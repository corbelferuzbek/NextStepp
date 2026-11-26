# NextStep + Maktab Bot integratsiyasi

Ushbu papkada NextStep Flask backend/frontend va `telegram_bot/` ichida aiogram 3 bot mavjud.

## Arxitektura
- NextStep — foydalanuvchi, musobaqa, coin balansi va coin ledger uchun yagona asosiy ma'lumotlar manbai.
- Telegram bot — NextStep API bilan ishlaydigan qo'shimcha interfeys.
- Botning alohida SQLite bazasi NextStep coinlarini saqlamaydi.

## 1. NextStep server sozlamalari
Render Environment Variables: `SECRET_KEY`, `ADMIN_LOGIN`, `ADMIN_PASSWORD`, `BOT_API_KEY`, `DATABASE_URL`, `FLASK_ENV=production`. `BOT_API_KEY` uchun kuchli tasodifiy maxfiy qiymat yarating.

Build: `pip install -r backend/requirements.txt`
Start: `gunicorn --chdir backend app:app --bind 0.0.0.0:$PORT`

## 2. Telegram bot sozlamalari
`telegram_bot/.env.example` nusxasini `.env` qiling va to'ldiring:
- `BOT_TOKEN` — BotFather tokeni
- `OWNER_ID` — bot egasining Telegram ID si
- `NEXTSTEP_API_URL` — NextStep deploy qilingan URL, oxirida slash qo'ymang
- `NEXTSTEP_API_KEY` — NextStep serveridagi `BOT_API_KEY` bilan aynan bir xil
- `SITE_API_KEY` — botga NextStep saytidan e'lon yuborish uchun avvalgi kalit

Bot build: `pip install -r requirements.txt`
Bot start: `python main.py`

## 3. Telegram hisobini bog'lash
1. Foydalanuvchi NextStep saytida email/parol bilan ro'yxatdan o'tadi yoki tizimga kiradi.
2. Telegram botda `/myid` yuboradi.
3. Saytning Profil bo'limida Telegram ID ni kiritib, «Telegramni bog'lash» tugmasini bosadi.
4. Endi botdagi 🚀 NextStep menyusidan wallet, coin tarixi, musobaqalar va ro'yxatdan o'tish ishlaydi.

## 4. Bot menyusi
- 🪙 Coin hamyonim — NextStep dagi joriy balans
- 📜 Coin tarixi — so'nggi coin tranzaksiyalari
- 🏁 Musobaqalar — musobaqalar ro'yxati
- Qatnashish — NextStep musobaqasiga ro'yxatdan o'tish

## Muhim xavfsizlik
- `BOT_API_KEY`, `BOT_TOKEN`, `.env` fayllarini GitHub'ga joylamang.
- Oldin arxivlarda bo'lgan `.env` ichidagi token/parollarni rotatsiya qiling.
- `BOT_API_KEY` faqat server Environment Variables va bot `.env` ichida bo'lsin.
- SQLite ishlatilsa Render Persistent Disk kerak; ko'p foydalanuvchi uchun PostgreSQL tavsiya qilinadi.
- Botning `/myid` ko'rsatgan ID si faqat foydalanuvchining o'zi NextStep hisobiga bog'lashi uchun ishlatiladi.

## API endpointlar
- `GET /api/integrations/telegram/contests`
- `GET /api/integrations/telegram/wallet/<telegram_id>`
- `POST /api/integrations/telegram/contests/<contest_id>/register`
- `POST /api/me/telegram` (JWT Bearer token bilan)


## Yagona .env sozlamasi

Loyiha asosiy papkasidagi `.env.example` faylini `.env` deb nusxalang va barcha qiymatlarni kiriting. Backend (`backend/app.py`) ham, bot (`telegram_bot/config.py`) ham aynan shu root `.env` faylini o'qiydi. Alohida `backend/.env` yoki `telegram_bot/.env` kerak emas.

`BOT_API_KEY` va `NEXTSTEP_API_KEY` bir xil bo'lishi kerak. `SITE_API_KEY` esa botning e'lon API'si uchun alohida kalit. `PORT` Flask uchun, `BOT_PORT` botning mini-API serveri uchun ishlatiladi. `OWNER_ID` vergul bilan ajratilgan bir nechta Telegram ID qabul qiladi; birinchi ID bosh admin hisoblanadi.

Ishga tushirish: loyiha papkasida `.env` ni to'ldiring, so'ng `cd backend` va `python app.py` buyrug'ini bajaring. Flask debug rejimida bot faqat serving child processda ishga tushadi.
