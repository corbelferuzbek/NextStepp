import json

import aiosqlite

from config import DB_PATH, OWNER_ID, OWNER_IDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_active TEXT
);
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    options TEXT NOT NULL,
    correct INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    total INTEGER NOT NULL,
    finished_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS poll_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    option_index INTEGER NOT NULL,
    voted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(poll_id, user_id)
);
CREATE TABLE IF NOT EXISTS surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS survey_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    question_type TEXT NOT NULL CHECK(question_type IN ('choice', 'text')),
    options TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS survey_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    survey_id INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    answers TEXT NOT NULL,
    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(survey_id, user_id)
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_BEST = "SELECT user_id, quiz_id, MAX(score) AS b FROM results GROUP BY user_id, quiz_id"
_TOTALS = f"WITH best AS ({_BEST}), tot AS (SELECT user_id, SUM(b) AS p, COUNT(*) AS q FROM best GROUP BY user_id)"


async def _connect():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


async def init_db():
    db = await _connect()
    try:
        await db.executescript(SCHEMA)
 
        cur = await db.execute("PRAGMA table_info(users)")
        columns = {r["name"] for r in await cur.fetchall()}
        if "last_active" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        for owner_id in OWNER_IDS:
            await db.execute("INSERT OR IGNORE INTO admins (id) VALUES (?)", (owner_id,))
        await db.commit()
    finally:
        await db.close()


async def _run(sql, params=(), fetch=None):
    db = await _connect()
    try:
        cur = await db.execute(sql, params)
        await db.commit()
        if fetch == "one":
            return await cur.fetchone()
        if fetch == "all":
            return await cur.fetchall()
        return cur.lastrowid
    finally:
        await db.close()



async def upsert_user(user_id, full_name, username):
    """Foydalanuvchini saqlaydi. Yangi bo'lsa True qaytaradi."""
    db = await _connect()
    try:
        cur = await db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        exists = await cur.fetchone() is not None
        if exists:
            await db.execute(
                "UPDATE users SET full_name = ?, username = ?, last_active = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (full_name, username, user_id),
            )
        else:
            await db.execute(
                "INSERT INTO users (id, full_name, username, last_active) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (user_id, full_name, username),
            )
        await db.commit()
        return not exists
    finally:
        await db.close()


async def touch_user(user_id):
    await _run("UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


async def get_user(user_id):
    return await _run(
        "SELECT id, full_name, username, joined_at FROM users WHERE id = ?", (user_id,), fetch="one"
    )


async def all_user_ids():
    rows = await _run("SELECT id FROM users", fetch="all")
    return [r["id"] for r in rows]


async def count_users():
    row = await _run("SELECT COUNT(*) AS c FROM users", fetch="one")
    return row["c"]


async def stats():
    queries = {
        "users": "SELECT COUNT(*) AS c FROM users",
        "new_24h": "SELECT COUNT(*) AS c FROM users WHERE joined_at >= datetime('now', '-1 day')",
        "active_24h": "SELECT COUNT(*) AS c FROM users WHERE last_active >= datetime('now', '-1 day')",
        "quizzes": "SELECT COUNT(*) AS c FROM quizzes",
        "attempts": "SELECT COUNT(*) AS c FROM results",
        "announcements": "SELECT COUNT(*) AS c FROM announcements",
    }
    db = await _connect()
    try:
        out = {}
        for key, sql in queries.items():
            cur = await db.execute(sql)
            out[key] = (await cur.fetchone())["c"]
        return out
    finally:
        await db.close()



async def is_admin(user_id):
    row = await _run("SELECT 1 FROM admins WHERE id = ?", (user_id,), fetch="one")
    return row is not None


async def add_admin(user_id):
    await _run("INSERT OR IGNORE INTO admins (id) VALUES (?)", (user_id,))


async def remove_admin(user_id):
    await _run("DELETE FROM admins WHERE id = ?", (user_id,))


async def list_admins():
    rows = await _run("SELECT id FROM admins", fetch="all")
    return [r["id"] for r in rows]


# ---- quizlar ----
async def create_quiz(title, questions):
    db = await _connect()
    try:
        cur = await db.execute("INSERT INTO quizzes (title) VALUES (?)", (title,))
        quiz_id = cur.lastrowid
        for q in questions:
            await db.execute(
                "INSERT INTO questions (quiz_id, text, options, correct) VALUES (?, ?, ?, ?)",
                (quiz_id, q["text"], json.dumps(q["options"], ensure_ascii=False), q["correct"]),
            )
        await db.commit()
        return quiz_id
    finally:
        await db.close()


async def list_quizzes(user_id=0, limit=20):
    return await _run(
        """
        SELECT q.id, q.title,
               (SELECT COUNT(*) FROM questions WHERE quiz_id = q.id) AS n,
               EXISTS(SELECT 1 FROM results r WHERE r.quiz_id = q.id AND r.user_id = ?) AS done
        FROM quizzes q ORDER BY q.id DESC LIMIT ?
        """,
        (user_id, limit),
        fetch="all",
    )


async def get_quiz(quiz_id):
    return await _run("SELECT id, title FROM quizzes WHERE id = ?", (quiz_id,), fetch="one")


async def delete_quiz(quiz_id):
    await _run("DELETE FROM quizzes WHERE id = ?", (quiz_id,))


async def get_questions(quiz_id):
    rows = await _run(
        "SELECT text, options, correct FROM questions WHERE quiz_id = ? ORDER BY id",
        (quiz_id,),
        fetch="all",
    )
    return [
        {"text": r["text"], "options": json.loads(r["options"]), "correct": r["correct"]}
        for r in rows
    ]



async def save_result(quiz_id, user_id, score, total):
    await _run(
        "INSERT INTO results (quiz_id, user_id, score, total) VALUES (?, ?, ?, ?)",
        (quiz_id, user_id, score, total),
    )


async def top_results(limit=10):
    return await _run(
        f"{_TOTALS} SELECT u.full_name AS name, tot.p AS points, tot.q AS quizzes "
        "FROM tot JOIN users u ON u.id = tot.user_id ORDER BY tot.p DESC, tot.q ASC, u.id ASC LIMIT ?",
        (limit,),
        fetch="all",
    )


async def user_progress(user_id):
    """Umumiy ball, yechilgan quizlar soni, reytingdagi o'rin."""
    return await _run(
        f"{_TOTALS} SELECT p AS points, q AS quizzes, "
        "(SELECT COUNT(*) FROM tot t2 WHERE t2.p > tot.p) + 1 AS place, "
        "(SELECT COUNT(*) FROM tot) AS n FROM tot WHERE user_id = ?",
        (user_id,),
        fetch="one",
    )


async def quiz_place(quiz_id, user_id):
    """Foydalanuvchining ushbu quiz bo'yicha o'rni."""
    return await _run(
        """
        WITH best AS (
            SELECT user_id, MAX(score) AS b FROM results WHERE quiz_id = ? GROUP BY user_id
        )
        SELECT (SELECT COUNT(*) FROM best x WHERE x.b > best.b) + 1 AS place,
               (SELECT COUNT(*) FROM best) AS n
        FROM best WHERE user_id = ?
        """,
        (quiz_id, user_id),
        fetch="one",
    )


async def export_results():
    return await _run(
        """
        SELECT u.full_name, u.username, qz.title, r.score, r.total, r.finished_at
        FROM results r
        JOIN users u ON u.id = r.user_id
        JOIN quizzes qz ON qz.id = r.quiz_id
        ORDER BY r.id
        """,
        fetch="all",
    )


# ---- e'lonlar ----
async def add_announcement(title, text, url=None):
    return await _run(
        "INSERT INTO announcements (title, text, url) VALUES (?, ?, ?)", (title, text, url)
    )


async def latest_announcements(limit=5):
    return await _run(
        "SELECT title, text, url, created_at FROM announcements ORDER BY id DESC LIMIT ?",
        (limit,),
        fetch="all",
    )
# ========== SO'ROVNOMALAR ==========

async def create_poll(title, question, options):
    return await _run(
        """
        INSERT INTO polls (title, question, options)
        VALUES (?, ?, ?)
        """,
        (title, question, json.dumps(options, ensure_ascii=False))
    )


async def list_polls(limit=30):
    return await _run(
        """
        SELECT id, title, question
        FROM polls
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
        fetch="all"
    )


async def get_poll(poll_id):
    row = await _run(
        """
        SELECT id, title, question, options
        FROM polls
        WHERE id = ?
        """,
        (poll_id,),
        fetch="one"
    )

    if not row:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "question": row["question"],
        "options": json.loads(row["options"])
    }


async def cast_poll_vote(poll_id, user_id, option_index):
    conn = await _connect()

    try:
        await conn.execute(
            """
            INSERT INTO poll_votes
            (poll_id, user_id, option_index)
            VALUES (?, ?, ?)
            """,
            (poll_id, user_id, option_index)
        )

        await conn.commit()
        return True

    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            return False
        raise

    finally:
        await conn.close()


async def has_voted(poll_id, user_id):
    result = await _run(
        """
        SELECT 1
        FROM poll_votes
        WHERE poll_id = ? AND user_id = ?
        """,
        (poll_id, user_id),
        fetch="one"
    )

    return result is not None


async def poll_results(poll_id):
    poll = await get_poll(poll_id)

    if not poll:
        return None

    rows = await _run(
        """
        SELECT option_index, COUNT(*) AS n
        FROM poll_votes
        WHERE poll_id = ?
        GROUP BY option_index
        """,
        (poll_id,),
        fetch="all"
    )

    counts = [0] * len(poll["options"])

    for row in rows:
        index = row["option_index"]

        if 0 <= index < len(counts):
            counts[index] = row["n"]

    return {
        "poll": poll,
        "counts": counts,
        "total": sum(counts)
    }


async def delete_poll(poll_id):
    return await _run(
        "DELETE FROM polls WHERE id = ?",
        (poll_id,)
    )


# ---- Ko'p savolli so'rovnomalar ----
async def create_survey(title, questions):
    """Savollar ro'yxati bilan yangi so'rovnoma yaratadi."""
    conn = await _connect()
    try:
        cur = await conn.execute(
            "INSERT INTO surveys (title) VALUES (?)",
            (title,)
        )
        survey_id = cur.lastrowid
        for position, question in enumerate(questions):
            await conn.execute(
                """
                INSERT INTO survey_questions
                    (survey_id, position, text, question_type, options)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    survey_id,
                    position,
                    question["text"],
                    question["type"],
                    json.dumps(question.get("options", []), ensure_ascii=False)
                )
            )
        await conn.commit()
        return survey_id
    finally:
        await conn.close()


async def list_surveys(user_id=0, limit=30):
    return await _run(
        """
        SELECT s.id, s.title,
               (SELECT COUNT(*) FROM survey_questions q WHERE q.survey_id=s.id) AS n,
               EXISTS(
                   SELECT 1 FROM survey_responses r
                   WHERE r.survey_id=s.id AND r.user_id=?
               ) AS done
        FROM surveys s
        ORDER BY s.id DESC
        LIMIT ?
        """,
        (user_id, limit),
        fetch="all"
    )


async def get_survey(survey_id):
    survey = await _run(
        "SELECT id, title FROM surveys WHERE id=?",
        (survey_id,),
        fetch="one"
    )
    if not survey:
        return None
    rows = await _run(
        """
        SELECT id, text, question_type, options
        FROM survey_questions
        WHERE survey_id=?
        ORDER BY position, id
        """,
        (survey_id,),
        fetch="all"
    )
    return {
        "id": survey["id"],
        "title": survey["title"],
        "questions": [
            {
                "id": row["id"],
                "text": row["text"],
                "type": row["question_type"],
                "options": json.loads(row["options"] or "[]")
            }
            for row in rows
        ]
    }


async def has_completed_survey(survey_id, user_id):
    row = await _run(
        "SELECT 1 FROM survey_responses WHERE survey_id=? AND user_id=?",
        (survey_id, user_id),
        fetch="one"
    )
    return row is not None


async def save_survey_response(survey_id, user_id, answers):
    conn = await _connect()
    try:
        await conn.execute(
            """
            INSERT INTO survey_responses (survey_id, user_id, answers)
            VALUES (?, ?, ?)
            """,
            (survey_id, user_id, json.dumps(answers, ensure_ascii=False))
        )
        await conn.commit()
        return True
    except Exception as error:
        if "UNIQUE constraint failed" in str(error):
            return False
        raise
    finally:
        await conn.close()


async def survey_results(survey_id):
    survey = await get_survey(survey_id)
    if not survey:
        return None
    rows = await _run(
        "SELECT user_id, answers, submitted_at FROM survey_responses WHERE survey_id=? ORDER BY id",
        (survey_id,),
        fetch="all"
    )
    responses = [
        {
            "user_id": row["user_id"],
            "answers": json.loads(row["answers"]),
            "submitted_at": row["submitted_at"]
        }
        for row in rows
    ]
    return {"survey": survey, "responses": responses, "total": len(responses)}
