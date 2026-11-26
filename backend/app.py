"""
CodeLab backend — single-file Flask app.
Ishga tushirish:  python app.py
Docker:           docker compose up
"""
import os, json, hmac, subprocess, sys, atexit, logging
from datetime import datetime, date, timedelta, timezone
from functools import wraps
import time, re
from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import jwt
import requests as http

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=False)

# ============================================================
# CONFIG
# ============================================================
class Config:
    SECRET_KEY              = os.getenv("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///codelab.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    AI_PROVIDER  = os.getenv("AI_PROVIDER", "")
    AI_API_KEY   = os.getenv("AI_API_KEY", "")
    AI_MODEL     = os.getenv("AI_MODEL", "")
    BOT_API_KEY  = os.getenv("BOT_API_KEY", "")
    DEV_MODE     = os.getenv("FLASK_ENV", "development") == "development"
    FRONTEND_DIR = os.getenv("FRONTEND_DIR",
                             os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"))

# ============================================================
# DB
# ============================================================
db = SQLAlchemy()

class JsonMixin:
    def _json(self, col):
        v = getattr(self, col)
        return json.loads(v) if v else None
    def _set_json(self, col, val):
        setattr(self, col, json.dumps(val) if val is not None else None)


class User(db.Model):
    __tablename__ = "users"
    id          = db.Column(db.Integer, primary_key=True)
    tg_id       = db.Column(db.BigInteger, unique=True, nullable=True)  # eski bazalar bilan moslik uchun
    email       = db.Column(db.String(254), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    username    = db.Column(db.String(64), nullable=True)
    first_name  = db.Column(db.String(120), nullable=True)
    last_name   = db.Column(db.String(120), nullable=True)
    name        = db.Column(db.String(120), nullable=False)
    role        = db.Column(db.String(20), default="user")
    coins       = db.Column(db.Integer, default=0)
    streak      = db.Column(db.Integer, default=0)
    last_active = db.Column(db.Date, nullable=True)
    lang        = db.Column(db.String(5), default="uz")
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class CoinTransaction(db.Model):
    """Coin balansining o'zgarmas auditi: har bir kirim/chiqim alohida yoziladi."""
    __tablename__ = "coin_transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(160), nullable=False)
    source = db.Column(db.String(40), nullable=False, default="system")
    reference_id = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class Field(db.Model):
    __tablename__ = "fields"
    id      = db.Column(db.Integer, primary_key=True)
    icon    = db.Column(db.String(10), default="📘")
    name_uz = db.Column(db.String(120))
    name_en = db.Column(db.String(120))
    name_ru = db.Column(db.String(120))

    def to_dict(self):
        return {"id": self.id, "icon": self.icon,
                "name": {"uz": self.name_uz, "en": self.name_en, "ru": self.name_ru}}


class Course(db.Model):
    __tablename__ = "courses"
    id       = db.Column(db.Integer, primary_key=True)
    field_id = db.Column(db.Integer, db.ForeignKey("fields.id"), nullable=False)
    title    = db.Column(db.String(160), nullable=False)
    topics   = db.relationship("Topic", backref="course", cascade="all, delete-orphan")

    def to_dict(self, include_topics=False):
        d = {"id": self.id, "field": self.field_id, "title": self.title,
             "topic_count": len(self.topics)}
        if include_topics:
            d["topics"] = [t.to_dict(with_questions=True) for t in self.topics]
        return d


class Topic(db.Model, JsonMixin):
    __tablename__ = "topics"
    id             = db.Column(db.Integer, primary_key=True)
    course_id      = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title          = db.Column(db.String(200), nullable=False)
    video          = db.Column(db.String(500), default="")
    coins          = db.Column(db.Integer, default=10)
    questions_json = db.Column(db.Text, default="[]")

    @property
    def questions(self):
        return self._json("questions_json") or []

    @questions.setter
    def questions(self, v):
        self._set_json("questions_json", v)

    def to_dict(self, with_questions=False):
        d = {"id": self.id, "course": self.course_id, "title": self.title,
             "video": self.video, "coins": self.coins,
             "question_count": len(self.questions)}
        if with_questions:
            # Public payload deliberately excludes the correct answer index.
            d["questions"] = [{"q": q.get("q", ""), "o": q.get("o", [])}
                               for q in self.questions]
        return d


class Progress(db.Model):
    __tablename__ = "progress"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic_id   = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    done       = db.Column(db.Boolean, default=False)
    best_score = db.Column(db.Integer, nullable=True)
    attempts   = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "topic_id"),)


class Certificate(db.Model):
    __tablename__ = "certificates"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id  = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    contest_id = db.Column(db.Integer, db.ForeignKey("contests.id"), nullable=True)
    issued_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "course_id", "contest_id"),)


class Mentor(db.Model):
    __tablename__ = "mentors"
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(120))
    spec    = db.Column(db.String(120))
    tg_id   = db.Column(db.BigInteger, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class Question(db.Model):
    __tablename__ = "questions"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    topic_id    = db.Column(db.Integer, db.ForeignKey("topics.id"), nullable=False)
    mentor_id   = db.Column(db.Integer, db.ForeignKey("mentors.id"), nullable=False)
    text        = db.Column(db.Text, nullable=False)
    answer      = db.Column(db.Text, nullable=True)
    answered_at = db.Column(db.DateTime, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Contest(db.Model, JsonMixin):
    __tablename__ = "contests"
    id             = db.Column(db.Integer, primary_key=True)
    title          = db.Column(db.String(200))
    status         = db.Column(db.String(20), default="upcoming")
    reward         = db.Column(db.String(20), default="coin")
    coins          = db.Column(db.Integer, default=50)
    questions_json = db.Column(db.Text, default="[]")
    created_at     = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def questions(self):
        return self._json("questions_json") or []

    @questions.setter
    def questions(self, v):
        self._set_json("questions_json", v)

    def to_dict(self, with_questions=False):
        d = {"id": self.id, "title": self.title, "status": self.status,
             "reward": self.reward, "coins": self.coins}
        if with_questions:
            d["questions"] = [{"q": q.get("q", ""), "o": q.get("o", [])}
                               for q in self.questions]
        return d


class ContestEntry(db.Model):
    __tablename__ = "contest_entries"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    contest_id   = db.Column(db.Integer, db.ForeignKey("contests.id"), nullable=False)
    score        = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "contest_id"),)


class Badge(db.Model):
    __tablename__ = "badges"
    id      = db.Column(db.Integer, primary_key=True)
    code    = db.Column(db.String(40), unique=True)
    icon    = db.Column(db.String(10))
    name_uz = db.Column(db.String(120))
    name_en = db.Column(db.String(120))
    name_ru = db.Column(db.String(120))


class UserBadge(db.Model):
    __tablename__ = "user_badges"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    badge_id   = db.Column(db.Integer, db.ForeignKey("badges.id"), nullable=False)
    awarded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint("user_id", "badge_id"),)


class Rule(db.Model):
    __tablename__ = "rules"
    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(40), unique=True)
    value = db.Column(db.String(200))

    @staticmethod
    def get(key, default=None):
        r = Rule.query.filter_by(key=key).first()
        return r.value if r else default

    @staticmethod
    def set(key, value):
        r = Rule.query.filter_by(key=key).first()
        if r: r.value = str(value)
        else: db.session.add(Rule(key=key, value=str(value)))


# ============================================================
# AUTH
# ============================================================
TOKEN_MAX_AGE = 60 * 60 * 24 * 30
JWT_ALGORITHM = "HS256"


def issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_MAX_AGE),
        "type": "access",
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=JWT_ALGORITHM)


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token_value = header.partition(" ")
        tk = token_value.strip() if scheme.lower() == "bearer" else ""
        try:
            if not tk:
                raise jwt.InvalidTokenError("Missing bearer token")
            data = jwt.decode(
                tk, Config.SECRET_KEY, algorithms=[JWT_ALGORITHM],
                options={"require": ["sub", "iat", "exp"]},
            )
            if data.get("type") != "access":
                raise jwt.InvalidTokenError("Invalid token type")
            g.user = db.session.get(User, int(data["sub"]))
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            g.user = None
        if not g.user:
            return jsonify(error="unauthorized"), 401
        today = date.today()
        if g.user.last_active != today:
            if g.user.last_active == today - timedelta(days=1):
                g.user.streak = (g.user.streak or 0) + 1
            else:
                g.user.streak = 1
            g.user.last_active = today
            db.session.commit()
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    @require_auth
    def wrapper(*args, **kwargs):
        if g.user.role != "admin":
            return jsonify(error="forbidden"), 403
        return f(*args, **kwargs)
    return wrapper


def require_mentor_or_admin(f):
    @wraps(f)
    @require_auth
    def wrapper(*args, **kwargs):
        if g.user.role not in ("admin", "mentor"):
            return jsonify(error="forbidden"), 403
        return f(*args, **kwargs)
    return wrapper


# ============================================================
# AI
# ============================================================
SYSTEM_PROMPT = ("Sen {topic} mavzusida o'qituvchisan. Foydalanuvchi tilida ({lang}) "
                 "qisqa, aniq, kod misollari bilan javob ber.")


def ai_ask(question: str, topic: str, lang: str = "uz") -> str:
    if not Config.AI_API_KEY:
        return "⚠️ AI sozlanmagan. Admin .env faylida AI_API_KEY ni to'ldirsin."
    sys_msg = SYSTEM_PROMPT.format(topic=topic or "dasturlash", lang=lang)
    try:
        if Config.AI_PROVIDER == "gemini":
            model = Config.AI_MODEL or "gemini-1.5-flash"
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{model}:generateContent?key={Config.AI_API_KEY}")
            r = http.post(url, json={"contents": [{"parts": [
                {"text": f"{sys_msg}\n\nSavol: {question}"}]}]}, timeout=30)
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

        base = "https://api.groq.com/openai" if Config.AI_PROVIDER == "groq" else "https://api.openai.com"
        model = Config.AI_MODEL or ("llama-3.1-70b-versatile" if Config.AI_PROVIDER == "groq" else "gpt-4o-mini")
        r = http.post(f"{base}/v1/chat/completions",
                      headers={"Authorization": f"Bearer {Config.AI_API_KEY}"},
                      json={"model": model, "temperature": 0.5, "messages": [
                          {"role": "system", "content": sys_msg},
                          {"role": "user", "content": question}]},
                      timeout=30)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        app.logger.exception("AI provider request failed")
        return "AI xizmatida vaqtinchalik xatolik. Keyinroq qayta urinib ko'ring."


# ============================================================
# SEED
# ============================================================
def seed_if_empty():
    if Field.query.first():
        return

    f_web = Field(icon="🌐", name_uz="Veb dasturlash", name_en="Web development", name_ru="Веб-разработка")
    f_py  = Field(icon="🐍", name_uz="Python", name_en="Python", name_ru="Python")
    f_ds  = Field(icon="🎨", name_uz="Dizayn", name_en="Design", name_ru="Дизайн")
    db.session.add_all([f_web, f_py, f_ds]); db.session.flush()

    c1 = Course(field_id=f_web.id, title="HTML & CSS")
    c2 = Course(field_id=f_py.id,  title="Python Basics")
    c3 = Course(field_id=f_ds.id,  title="Figma UI")
    db.session.add_all([c1, c2, c3]); db.session.flush()

    def Q(q, *opts, c):
        return {"q": q, "o": list(opts), "c": c - 1}

    db.session.add_all([
        Topic(course_id=c1.id, title="Tags and structure", video="", coins=10, questions=[
            Q("Which tag creates a link?", "<a>", "<p>", "<div>", c=1),
            Q("Biggest heading tag?", "<h6>", "<h1>", "<head>", c=2)]),
        Topic(course_id=c1.id, title="CSS selectors", video="", coins=10, questions=[
            Q("Which symbol selects a class?", "#", ".", "*", c=2),
            Q("Which property changes text color?", "color", "font", "size", c=1)]),
        Topic(course_id=c1.id, title="Flexbox", video="", coins=15, questions=[
            Q("Which display value enables flexbox?", "block", "flex", "grid", c=2),
            Q("Center items on main axis?", "align-items", "justify-content", "gap", c=2)]),
        Topic(course_id=c2.id, title="Variables", video="", coins=10, questions=[
            Q("Which is a valid variable name?", "my_var", "2var", "my-var", c=1),
            Q("print(2 ** 3) = ?", "6", "8", "9", c=2)]),
        Topic(course_id=c2.id, title="Loops", video="", coins=10, questions=[
            Q("Which keyword loops over a list?", "for", "if", "def", c=1),
            Q("range(3) gives?", "1,2,3", "0,1,2", "0,1,2,3", c=2)]),
    ])
    db.session.flush()

    db.session.add_all([
        Mentor(name="Dilnoza A.", spec="Frontend"),
        Mentor(name="Sardor B.", spec="Python"),
    ])

    db.session.add(Contest(title="Weekend IT Cup", status="active", reward="both", coins=50, questions=[
        Q("HTML stands for?", "HyperText Markup Language", "High Tech Modern Language", "Home Tool Markup Language", c=1),
        Q("Python list literal?", "(1,2)", "[1,2]", "{1,2}", c=2)]))

    db.session.add_all([
        Badge(code="first_lesson", icon="🎯", name_uz="Birinchi qadam", name_en="First step", name_ru="Первый шаг"),
        Badge(code="first_cert",   icon="🏅", name_uz="Birinchi sertifikat", name_en="First certificate", name_ru="Первый сертификат"),
        Badge(code="streak_7",     icon="🔥", name_uz="7 kunlik seriya", name_en="7-day streak", name_ru="Серия 7 дней"),
        Badge(code="streak_30",    icon="💎", name_uz="30 kunlik seriya", name_en="30-day streak", name_ru="Серия 30 дней"),
        Badge(code="coins_100",    icon="💰", name_uz="100 coin", name_en="100 coins", name_ru="100 монет"),
        Badge(code="coins_1000",   icon="👑", name_uz="1000 coin", name_en="1000 coins", name_ru="1000 монет"),
    ])

    db.session.add(Rule(key="pass", value="60"))
    db.session.commit()


# ============================================================
# APP
# ============================================================
app = Flask(__name__,
            static_folder=os.path.join(Config.FRONTEND_DIR, "static"),
            static_url_path="/static",
            template_folder=Config.FRONTEND_DIR)
app.config.from_object(Config)
if not Config.DEV_MODE and (not Config.SECRET_KEY or Config.SECRET_KEY == "dev-secret-change-me"):
    raise RuntimeError("Production uchun kuchli SECRET_KEY ni .env ga kiriting")
if not Config.DEV_MODE and not Config.ADMIN_PASSWORD:
    raise RuntimeError("Production uchun ADMIN_PASSWORD ni .env ga kiriting")
db.init_app(app)
# Frontend same-origin served by Flask; unrestricted CORS is unnecessary.


def user_payload(user):
    badge_rows = (db.session.query(Badge).join(UserBadge)
                  .filter(UserBadge.user_id == user.id).all())
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
            "coins": user.coins, "streak": user.streak,
            "badges": [{"code": b.code, "icon": b.icon, "name": b.name_uz} for b in badge_rows]}


def progress_payload(user):
    rows = Progress.query.filter_by(user_id=user.id).all()
    return {str(r.topic_id): {"done": r.done, "score": r.best_score} for r in rows}


def cert_payload(user):
    out = []
    for c in Certificate.query.filter_by(user_id=user.id).all():
        if c.course_id:
            course = db.session.get(Course, c.course_id)
            out.append({"kind": "course", "id": c.course_id,
                        "title": course.title if course else "?"})
        elif c.contest_id:
            k = db.session.get(Contest, c.contest_id)
            out.append({"kind": "contest", "id": c.contest_id,
                        "title": k.title if k else "?"})
    return out


def add_coins(user, amount, reason, source="system", reference_id=None):
    """Balans va ledger yozuvini bir DB tranzaksiyasida yangilaydi."""
    amount = int(amount)
    if amount == 0:
        return
    if user.coins + amount < 0:
        raise ValueError("Coin balansi yetarli emas")
    user.coins += amount
    db.session.add(CoinTransaction(
        user_id=user.id, amount=amount, balance_after=user.coins,
        reason=str(reason)[:160], source=str(source)[:40],
        reference_id=str(reference_id)[:80] if reference_id is not None else None
    ))


def require_bot_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        configured = Config.BOT_API_KEY
        supplied = request.headers.get("X-API-Key", "")
        if not configured or not supplied or not hmac.compare_digest(supplied, configured):
            return jsonify(error="unauthorized"), 401
        return f(*args, **kwargs)
    return wrapper


def award_badge(user, code):
    b = Badge.query.filter_by(code=code).first()
    if not b: return
    if UserBadge.query.filter_by(user_id=user.id, badge_id=b.id).first(): return
    db.session.add(UserBadge(user_id=user.id, badge_id=b.id))


# ---------- auth ----------
@app.post("/api/auth/register")
def auth_register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()[:120]
    email = str(data.get("email") or "").strip().lower()[:254]
    password = str(data.get("password") or "")
    if len(name) < 2:
        return jsonify(error="Ism kamida 2 ta belgidan iborat bo‘lsin"), 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify(error="Email manzil noto‘g‘ri"), 400
    if len(password) < 8:
        return jsonify(error="Parol kamida 8 ta belgidan iborat bo‘lishi kerak"), 400
    if User.query.filter(db.func.lower(User.email) == email).first():
        return jsonify(error="Bu email allaqachon ro‘yxatdan o‘tgan"), 409
    user = User(name=name, email=email, password_hash=generate_password_hash(password), role="user")
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(error="Ro‘yxatdan o‘tishda xatolik. Qayta urinib ko‘ring."), 500
    return jsonify(token=issue_token(user.id), user=user_payload(user)), 201


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:254]
    password = str(data.get("password") or "")
    user = User.query.filter(db.func.lower(User.email) == email).first() if email else None
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify(error="Email yoki parol noto‘g‘ri"), 401
    return jsonify(token=issue_token(user.id), user=user_payload(user))


@app.post("/api/auth/admin")
def auth_admin():
    """Brauzerdan admin login/parol bilan kirish; credentiallar faqat .env dan olinadi."""
    if not Config.ADMIN_LOGIN or not Config.ADMIN_PASSWORD:
        return jsonify(error="Admin login sozlanmagan (.env ni tekshiring)"), 503
    data = request.get_json(silent=True) or {}
    login = str(data.get("login") or "")
    password = str(data.get("password") or "")
    if not (hmac.compare_digest(login, Config.ADMIN_LOGIN) and
            hmac.compare_digest(password, Config.ADMIN_PASSWORD)):
        return jsonify(error="Login yoki parol noto'g'ri"), 401
    user = User.query.filter_by(tg_id=-3).first()
    if not user:
        user = User(tg_id=-3, name="Ozodov Admin", role="admin")
        db.session.add(user)
    user.name = "Ozodov Admin"
    user.role = "admin"
    db.session.commit()
    return jsonify(token=issue_token(user.id), user=user_payload(user))



@app.get("/api/me")
@require_auth
def me():
    contest_scores = {str(r.contest_id): r.score for r in
                      ContestEntry.query.filter_by(user_id=g.user.id).all()}
    return jsonify(user=user_payload(g.user),
                   progress=progress_payload(g.user),
                   certificates=cert_payload(g.user),
                   contest_scores=contest_scores,
                   streak={"count": g.user.streak,
                           "last": g.user.last_active.isoformat() if g.user.last_active else None})


# ---------- Telegram integration (private server-to-server API) ----------
@app.post("/api/me/telegram")
@require_auth
def link_telegram_account():
    data = request.get_json(silent=True) or {}
    tg_id = data.get("telegram_id")
    try:
        tg_id = int(tg_id)
        if tg_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(error="telegram_id noto'g'ri"), 400
    existing = User.query.filter(User.tg_id == tg_id, User.id != g.user.id).first()
    if existing:
        return jsonify(error="Bu Telegram akkaunt boshqa hisobga bog'langan"), 409
    g.user.tg_id = tg_id
    db.session.commit()
    return jsonify(ok=True, telegram_id=tg_id)


@app.get("/api/integrations/telegram/contests")
@require_bot_api_key
def bot_list_contests():
    rows = Contest.query.order_by(Contest.created_at.desc()).all()
    return jsonify([{
        "id": c.id, "title": c.title, "status": c.status,
        "reward": c.reward, "coins": c.coins
    } for c in rows])


@app.get("/api/integrations/telegram/wallet/<int:telegram_id>")
@require_bot_api_key
def bot_wallet(telegram_id):
    user = User.query.filter_by(tg_id=telegram_id).first()
    if not user:
        return jsonify(error="account_not_linked"), 404
    txs = CoinTransaction.query.filter_by(user_id=user.id).order_by(
        CoinTransaction.created_at.desc()).limit(50).all()
    return jsonify(
        user={"id": user.id, "name": user.name, "telegram_id": telegram_id},
        coins=user.coins,
        transactions=[{
            "id": t.id, "amount": t.amount, "balance_after": t.balance_after,
            "reason": t.reason, "source": t.source,
            "created_at": t.created_at.isoformat() + "Z"
        } for t in txs]
    )


@app.post("/api/integrations/telegram/contests/<int:contest_id>/register")
@require_bot_api_key
def bot_register_contest(contest_id):
    data = request.get_json(silent=True) or {}
    try:
        telegram_id = int(data.get("telegram_id"))
        if telegram_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(error="telegram_id noto'g'ri"), 400
    user = User.query.filter_by(tg_id=telegram_id).first()
    if not user:
        return jsonify(error="account_not_linked"), 404
    contest = db.session.get(Contest, contest_id)
    if not contest:
        return jsonify(error="contest_not_found"), 404
    if contest.status != "active":
        return jsonify(error="contest_not_open"), 409
    entry = ContestEntry.query.filter_by(user_id=user.id, contest_id=contest.id).first()
    if entry:
        return jsonify(error="already_registered"), 409
    db.session.add(ContestEntry(user_id=user.id, contest_id=contest.id))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(error="registration_failed"), 500
    return jsonify(ok=True, contest_id=contest.id, title=contest.title), 201


# ---------- content ----------
@app.get("/api/fields")
@require_auth
def list_fields():
    return jsonify([f.to_dict() for f in Field.query.all()])


@app.get("/api/courses")
@require_auth
def list_courses():
    field_id = request.args.get("field", type=int)
    q = Course.query
    if field_id: q = q.filter_by(field_id=field_id)
    return jsonify([c.to_dict() for c in q.all()])


@app.get("/api/courses/<int:cid>")
@require_auth
def get_course(cid):
    c = db.session.get(Course, cid)
    if not c: return jsonify(error="not found"), 404
    return jsonify(c.to_dict(include_topics=True))


@app.get("/api/topics/<int:tid>")
@require_auth
def get_topic(tid):
    t = db.session.get(Topic, tid)
    if not t: return jsonify(error="not found"), 404
    return jsonify(t.to_dict(with_questions=True))


# ---------- progress & quiz ----------
@app.post("/api/topics/<int:tid>/complete")
@require_auth
def complete_topic(tid):
    t = db.session.get(Topic, tid)
    if not t: return jsonify(error="not found"), 404
    p = Progress.query.filter_by(user_id=g.user.id, topic_id=tid).first()
    if not p:
        p = Progress(user_id=g.user.id, topic_id=tid)
        db.session.add(p)
    if not p.done:
        p.done = True
        if Progress.query.filter_by(user_id=g.user.id, done=True).count() <= 1:
            award_badge(g.user, "first_lesson")
        db.session.commit()
    return jsonify(ok=True)


@app.post("/api/topics/<int:tid>/quiz")
@require_auth
def submit_quiz(tid):
    t = db.session.get(Topic, tid)
    if not t: return jsonify(error="not found"), 404
    answers = (request.json or {}).get("answers", [])
    qs = t.questions
    if not qs: return jsonify(error="no questions"), 400
    if not isinstance(answers, list) or len(answers) != len(qs):
        return jsonify(error="invalid answers"), 400
    try:
        answers = [int(a) for a in answers]
    except (TypeError, ValueError):
        return jsonify(error="invalid answers"), 400
    if any(a < 0 or a >= len(q.get("o", [])) for a, q in zip(answers, qs)):
        return jsonify(error="invalid answer index"), 400
    if any(not isinstance(q, dict) or not isinstance(q.get("c"), int) for q in qs):
        return jsonify(error="quiz configuration invalid"), 500
    if any(not isinstance(q, dict) or not isinstance(q.get("c"), int) for q in qs):
        return jsonify(error="contest configuration invalid"), 500
    correct = sum(1 for i, q in enumerate(qs) if answers[i] == q["c"])
    pct = round(100 * correct / len(qs))
    pass_pct = int(Rule.get("pass", "60"))
    p = Progress.query.filter_by(user_id=g.user.id, topic_id=tid).first()
    if not p:
        p = Progress(user_id=g.user.id, topic_id=tid); db.session.add(p)
    p.attempts = (p.attempts or 0) + 1
    coins_awarded = 0
    if p.best_score is None or pct > p.best_score:
        p.best_score = pct
    if p.attempts == 1 and pct >= pass_pct:
        coins_awarded = t.coins if pct >= 90 else t.coins // 2
        add_coins(g.user, coins_awarded, f"Dars testi: {t.title}", "lesson", tid)
    db.session.commit()
    for code, cond in [("coins_100", g.user.coins >= 100),
                       ("coins_1000", g.user.coins >= 1000),
                       ("streak_7", (g.user.streak or 0) >= 7),
                       ("streak_30", (g.user.streak or 0) >= 30)]:
        if cond: award_badge(g.user, code)
    db.session.commit()
    return jsonify(pct=pct, correct=correct, total=len(qs),
                   coins=coins_awarded, pass_pct=pass_pct,
                   user_coins=g.user.coins)


# ---------- AI ----------
@app.post("/api/ai/ask")
@require_auth
def ai_endpoint():
    data = request.json or {}
    q = (data.get("q") or "").strip()
    tid = data.get("topic_id")
    if not q: return jsonify(error="empty question"), 400
    topic = db.session.get(Topic, tid) if tid else None
    return jsonify(answer=ai_ask(q, topic.title if topic else "", g.user.lang))


# ---------- mentor Q&A ----------
@app.get("/api/mentors")
@require_auth
def list_mentors():
    return jsonify([{"id": m.id, "name": m.name, "spec": m.spec} for m in Mentor.query.all()])


@app.post("/api/mentor/ask")
@require_auth
def mentor_ask():
    d = request.json or {}
    text = (d.get("q") or "").strip()
    if not text: return jsonify(error="empty"), 400
    mentor = db.session.get(Mentor, d.get("mentor_id"))
    topic = db.session.get(Topic, d.get("topic_id")) if d.get("topic_id") else None
    if not mentor or not topic:
        return jsonify(error="invalid mentor or topic"), 400
    q = Question(user_id=g.user.id, topic_id=topic.id,
                 mentor_id=mentor.id, text=text)
    db.session.add(q); db.session.commit()
    return jsonify(id=q.id, ok=True)


@app.get("/api/mentor/inbox")
@require_mentor_or_admin
def mentor_inbox():
    query = Question.query
    if g.user.role == "mentor":
        mentor = Mentor.query.filter_by(user_id=g.user.id).first()
        if not mentor:
            return jsonify([])
        query = query.filter_by(mentor_id=mentor.id)
    rows = query.order_by(Question.created_at.desc()).limit(100).all()
    out = []
    for r in rows:
        u = db.session.get(User, r.user_id)
        t_ = db.session.get(Topic, r.topic_id)
        out.append({"id": r.id, "text": r.text, "answer": r.answer,
                    "user": u.name if u else "?", "topic": t_.title if t_ else "?"})
    return jsonify(out)


@app.post("/api/mentor/<int:qid>/answer")
@require_mentor_or_admin
def mentor_answer(qid):
    q = db.session.get(Question, qid)
    if not q: return jsonify(error="not found"), 404
    if g.user.role == "mentor":
        mentor = Mentor.query.filter_by(user_id=g.user.id).first()
        if not mentor or q.mentor_id != mentor.id:
            return jsonify(error="forbidden"), 403
    answer = (request.json or {}).get("answer", "").strip()
    if not answer:
        return jsonify(error="empty answer"), 400
    q.answer = answer
    q.answered_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(ok=True)


# ---------- certificates ----------
@app.post("/api/certificates/course/<int:cid>")
@require_auth
def claim_cert(cid):
    c = db.session.get(Course, cid)
    if not c: return jsonify(error="not found"), 404
    pass_pct = int(Rule.get("pass", "60"))
    for t in c.topics:
        p = Progress.query.filter_by(user_id=g.user.id, topic_id=t.id).first()
        if not p or not p.done or (p.best_score or 0) < pass_pct:
            return jsonify(error="not_eligible"), 400
    if not Certificate.query.filter_by(user_id=g.user.id, course_id=cid).first():
        db.session.add(Certificate(user_id=g.user.id, course_id=cid))
        award_badge(g.user, "first_cert")
        db.session.commit()
    return jsonify(ok=True, title=c.title, name=g.user.name)


# ---------- contests ----------
@app.get("/api/contests")
@require_auth
def list_contests():
    return jsonify([k.to_dict() for k in Contest.query.order_by(Contest.created_at.desc()).all()])


@app.get("/api/contests/<int:kid>")
@require_auth
def get_contest(kid):
    k = db.session.get(Contest, kid)
    if not k: return jsonify(error="not found"), 404
    return jsonify(k.to_dict(with_questions=True))


@app.post("/api/contests/<int:kid>/submit")
@require_auth
def submit_contest(kid):
    k = db.session.get(Contest, kid)
    if not k or k.status != "active":
        return jsonify(error="not active"), 400
    existing_entry = ContestEntry.query.filter_by(user_id=g.user.id, contest_id=kid).first()
    if existing_entry and existing_entry.score is not None:
        return jsonify(error="already entered"), 400
    answers = (request.json or {}).get("answers", [])
    qs = k.questions
    if not qs or not isinstance(answers, list) or len(answers) != len(qs):
        return jsonify(error="invalid answers"), 400
    try:
        answers = [int(a) for a in answers]
    except (TypeError, ValueError):
        return jsonify(error="invalid answers"), 400
    if any(a < 0 or a >= len(q.get("o", [])) for a, q in zip(answers, qs)):
        return jsonify(error="invalid answer index"), 400
    correct = sum(1 for i, q in enumerate(qs) if answers[i] == q["c"])
    pct = round(100 * correct / len(qs)) if qs else 0
    if existing_entry:
        existing_entry.score = pct
        existing_entry.submitted_at = datetime.now(timezone.utc)
    else:
        db.session.add(ContestEntry(user_id=g.user.id, contest_id=kid, score=pct))
    pass_pct = int(Rule.get("pass", "60"))
    coins = 0
    if pct >= pass_pct and k.reward in ("coin", "both"):
        coins = k.coins
        add_coins(g.user, coins, f"Musobaqa mukofoti: {k.title}", "contest", kid)
    cert = pct >= pass_pct and k.reward in ("cert", "both")
    if cert and not Certificate.query.filter_by(user_id=g.user.id, contest_id=kid).first():
        db.session.add(Certificate(user_id=g.user.id, contest_id=kid))
        award_badge(g.user, "first_cert")
    db.session.commit()
    return jsonify(pct=pct, correct=correct, total=len(qs), coins=coins, cert=cert)


# ---------- badges / leaderboard ----------
@app.get("/api/me/coins/transactions")
@require_auth
def my_coin_transactions():
    rows = CoinTransaction.query.filter_by(user_id=g.user.id).order_by(
        CoinTransaction.created_at.desc()).limit(100).all()
    return jsonify([{
        "id": t.id, "amount": t.amount, "balance_after": t.balance_after,
        "reason": t.reason, "source": t.source,
        "created_at": t.created_at.isoformat() + "Z"
    } for t in rows])


@app.get("/api/badges")
@require_auth
def list_badges():
    mine = {ub.badge_id for ub in UserBadge.query.filter_by(user_id=g.user.id).all()}
    return jsonify([{"code": b.code, "icon": b.icon, "name": b.name_uz,
                     "earned": b.id in mine} for b in Badge.query.all()])


@app.get("/api/rules")
@require_auth
def public_rules():
    return jsonify({"pass": int(Rule.get("pass", "60"))})


@app.get("/api/leaderboard")
@require_auth
def leaderboard():
    top = User.query.order_by(User.coins.desc()).limit(20).all()
    return jsonify([{"id": u.id, "name": u.name, "coins": u.coins,
                     "streak": u.streak, "is_me": u.id == g.user.id} for u in top])


# ---------- admin ----------
@app.post("/api/admin/fields")
@require_admin
def admin_add_field():
    d = request.json or {}
    if not (d.get("name") or "").strip():
        return jsonify(error="name required"), 400
    db.session.add(Field(icon=d.get("icon", "📘"), name_uz=d["name"],
                         name_en=d["name"], name_ru=d["name"]))
    db.session.commit()
    return jsonify(ok=True)


@app.post("/api/admin/courses")
@require_admin
def admin_add_course():
    d = request.json or {}
    db.session.add(Course(field_id=d["field"], title=d["title"]))
    db.session.commit()
    return jsonify(ok=True)


@app.post("/api/admin/topics")
@require_admin
def admin_add_topic():
    d = request.json or {}
    db.session.add(Topic(course_id=d["course"], title=d["title"],
                         video=d.get("video", ""), coins=int(d.get("coins", 10)),
                         questions=d.get("questions", [])))
    db.session.commit()
    return jsonify(ok=True)


@app.post("/api/admin/mentors")
@require_admin
def admin_add_mentor():
    d = request.json or {}
    tg = d.get("tg_id")
    db.session.add(Mentor(name=d["name"], spec=d["spec"],
                          tg_id=int(tg) if tg else None))
    db.session.commit()
    return jsonify(ok=True)


@app.delete("/api/admin/mentors/<int:mid>")
@require_admin
def admin_del_mentor(mid):
    m = db.session.get(Mentor, mid)
    if m: db.session.delete(m); db.session.commit()
    return jsonify(ok=True)


@app.post("/api/admin/contests")
@require_admin
def admin_add_contest():
    d = request.json or {}
    db.session.add(Contest(title=d["title"], status="upcoming",
                           reward=d.get("reward", "coin"),
                           coins=int(d.get("coins", 50)),
                           questions=d.get("questions", [])))
    db.session.commit()
    return jsonify(ok=True)


@app.patch("/api/admin/contests/<int:kid>")
@require_admin
def admin_patch_contest(kid):
    k = db.session.get(Contest, kid)
    if not k: return jsonify(error="not found"), 404
    status = (request.json or {}).get("status")
    if status in ("upcoming", "active", "ended"):
        k.status = status
        db.session.commit()
        if status == "active": broadcast(f"🔴 Yangi musobaqa: {k.title}\nQatnashing!")
    return jsonify(ok=True)


@app.patch("/api/admin/rules")
@require_admin
def admin_rules():
    d = request.json or {}
    if "pass" in d: Rule.set("pass", d["pass"])
    db.session.commit()
    return jsonify(ok=True)


@app.get("/api/admin/analytics")
@require_admin
def admin_analytics():
    return jsonify(
        users=User.query.count(),
        active_today=User.query.filter_by(last_active=date.today()).count(),
        lessons_done=Progress.query.filter_by(done=True).count(),
        certs=Certificate.query.count(),
        contest_entries=ContestEntry.query.count())


def broadcast(text):
    # Botsiz versiyada Telegram xabarnomalari yuborilmaydi.
    return


# ---------- serve frontend ----------
@app.get("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


@app.get("/service-worker.js")
def service_worker():
    """Serve the PWA service worker from the frontend root scope."""
    return send_from_directory(app.template_folder, "service-worker.js", mimetype="application/javascript")


@app.get("/health")
def health():
    return jsonify(ok=True)


# ============================================================
# BOOT
# ============================================================
def ensure_user_identity_columns():
    """Eski SQLite bazalarda ham Telegram profil ustunlarini xavfsiz qo'shadi."""
    if db.engine.dialect.name != "sqlite":
        return
    with db.engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
        for col, sql_type in (("username", "VARCHAR(64)"), ("first_name", "VARCHAR(120)"), ("last_name", "VARCHAR(120)"), ("email", "VARCHAR(254)"), ("password_hash", "VARCHAR(255)")):
            if col not in cols:
                conn.exec_driver_sql(f"ALTER TABLE users ADD COLUMN {col} {sql_type}")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users(email)")

with app.app_context():
    db.create_all()
    ensure_user_identity_columns()
    seed_if_empty()


# ---------- optional Telegram bot sidecar ----------
_bot_process = None

def start_telegram_bot():
    """Start the Telegram bot alongside Flask when BOT_TOKEN is configured.

    Expected layout:
      project/
        backend/app.py
        telegram_bot/main.py
    The bot and backend both load the single project-root .env file. If BOT_TOKEN is absent, the website still starts.
    """
    global _bot_process
    bot_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "telegram_bot"))
    bot_main = os.path.join(bot_dir, "main.py")
    if not os.path.isfile(bot_main):
        app.logger.warning("Telegram bot topilmadi: %s. Faqat sayt ishga tushadi.", bot_main)
        return None

    # The shared project-root .env is loaded by this process and inherited by the bot.
    token = os.getenv("BOT_TOKEN")
    if not token:
        app.logger.warning("BOT_TOKEN yo'q. Sayt ishga tushadi, Telegram bot esa o'tkazib yuboriladi.")
        return None

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    try:
        _bot_process = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=bot_dir,
            env=env,
        )
        app.logger.info("Telegram bot alohida jarayonda ishga tushirildi (PID=%s).", _bot_process.pid)
        return _bot_process
    except Exception:
        app.logger.exception("Telegram botni ishga tushirib bo'lmadi")
        return None


def stop_telegram_bot():
    global _bot_process
    if _bot_process is not None and _bot_process.poll() is None:
        _bot_process.terminate()
        try:
            _bot_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _bot_process.kill()


atexit.register(stop_telegram_bot)


if __name__ == "__main__":
    # Flask's debug reloader launches the module twice. Start the bot only in
    # the serving child process to prevent duplicate Telegram polling sessions.
    if not Config.DEV_MODE or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_telegram_bot()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=Config.DEV_MODE)
