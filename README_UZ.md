# CodeLab — botsiz, email/parol orqali kirish

## Imkoniyatlar
- Foydalanuvchi email, ism-familiya va parol bilan ro‘yxatdan o‘tadi.
- Keyingi safar email va parol bilan tizimga kiradi.
- Parollar bazada ochiq matnda emas, xavfsiz hash ko‘rinishida saqlanadi.
- Ro‘yxatdan o‘tish va login javobida 30 kun amal qiladigan HS256 JWT access token qaytariladi.
- Frontend tokenni saqlaydi, foydalanuvchi ma’lumotlarini yuklaydi va avtomatik asosiy sahifaga (`#/`) o‘tadi.
- Bir email bilan ikki marta ro‘yxatdan o‘tish taqiqlanadi.
- Admin panel oddiy foydalanuvchi ro‘yxatidan alohida login/parol orqali ochiladi.
- Telegram bot, Telegram Mini App, Telegram tokeni yoki bot serveri talab qilinmaydi.

## Ishga tushirish (Windows)
1. Python 3.10+ o‘rnating.
2. Terminalda `cd NextStep_CodeLab/backend` buyrug‘ini bajaring.
3. Virtual muhit yarating: `python -m venv .venv`
4. Faollashtiring: `.venv\Scripts\activate`
5. Kutubxonalarni o‘rnating: `pip install -r requirements.txt`
6. Loyiha ildizidagi `.env.example` faylidan `.env` nusxa yarating.
7. `.env` ichida `SECRET_KEY`, `ADMIN_LOGIN`, `ADMIN_PASSWORD` qiymatlarini o‘zgartiring.
8. `python app.py` buyrug‘ini bajaring.
9. Brauzerda `http://127.0.0.1:5000` ni oching.

## Ro‘yxatdan o‘tish
- Ism va familiya
- Email manzil
- Kamida 8 belgili parol
- Parolni tasdiqlash

Ro‘yxatdan o‘tgandan keyin foydalanuvchi avtomatik tizimga kiradi. Keyingi tashrifda email va parol bilan kiradi.

## Eski ma’lumotlar bazasi
Dastur eski SQLite bazasidagi `users` jadvaliga `email` va `password_hash` ustunlarini avtomatik qo‘shadi. Eski Telegram akkauntlari email/parol hisobiga avtomatik aylanmaydi; ular yangi email bilan ro‘yxatdan o‘tishi kerak.

## JWT autentifikatsiyasi
- Har bir himoyalangan API so‘roviga `Authorization: Bearer <JWT>` sarlavhasi yuboriladi.
- Token muddati 30 kun; muddati tugasa foydalanuvchi qayta login qiladi.
- JWT imzosi backenddagi `SECRET_KEY` orqali HS256 algoritmida tekshiriladi.

## Xavfsizlik
- Productionda `FLASK_ENV=production` qiling va kuchli `SECRET_KEY` ishlating.
- `ADMIN_PASSWORD` ni kuchli va noyob parolga almashtiring.
- Saytni internetga joylashtirganda HTTPS yoqing.
- `.env` faylini GitHub yoki ZIP ichiga joylamang.


## Yangi tuzatishlar
- `requirements.txt` dagi `python-dotenv` va `PyJWT` ajratildi; Gunicorn qo'shildi.
- Coin tranzaksiyalari `coin_transactions` jadvalida audit qilinadi.
- `/api/me/coins/transactions` foydalanuvchining coin tarixini qaytaradi.
- Telegram bot uchun himoyalangan API: musobaqalar ro'yxati, wallet/ledger va musobaqaga ro'yxatdan o'tish.
- Foydalanuvchi tizimga kirganidan so'ng `POST /api/me/telegram` orqali Telegram ID sini hisobiga bog'lashi mumkin.
- Maxfiy `.env` arxivdan olib tashlandi; `.env.example` qo'shildi.

## Telegram bot API
Barcha bot so'rovlarida `X-API-Key: <BOT_API_KEY>` sarlavhasi bo'lishi shart.
- `GET /api/integrations/telegram/contests`
- `GET /api/integrations/telegram/wallet/<telegram_id>`
- `POST /api/integrations/telegram/contests/<contest_id>/register` JSON: `{"telegram_id": 123456789}`

Botda API kalitni kodga yozmang; hosting Environment Variables bo'limida `BOT_API_KEY` sifatida saqlang. Foydalanuvchi Telegram ID sini saytga login qilgan holda bog'lamaguncha wallet va musobaqa ro'yxatdan o'tkazish ishlamaydi.

## Render deployment
- Build: `pip install -r backend/requirements.txt`
- Start: `gunicorn --chdir backend app:app --bind 0.0.0.0:$PORT`
- Environment: `SECRET_KEY`, `ADMIN_LOGIN`, `ADMIN_PASSWORD`, `BOT_API_KEY`, `DATABASE_URL`, `FLASK_ENV=production`.
- SQLite ishlatilsa Render Persistent Disk ulang va `DATABASE_URL` ni diskdagi mutlaq SQLite yo'liga sozlang. Jiddiy production uchun PostgreSQL tavsiya etiladi.
- Eski `.env` qiymatlari arxivga kirgan bo'lishi mumkin: ularni yangilang/rotatsiya qiling va Git tarixidan ham olib tashlang.
