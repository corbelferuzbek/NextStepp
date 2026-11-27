NEXTSTEP — KO'P SAVOLLI SO'ROVNOMA YANGILANISHI

NIMALAR QO'SHILDI
- Admin /admin panelidan ko'p savolli so'rovnoma yaratadi.
- So'rovnoma nomi va istalgancha savol qo'shish mumkin.
- Har bir savol: variantli (2–8 variant) yoki erkin matnli.
- Foydalanuvchi /sorovnomalar orqali so'rovnomani tanlab, savollarga navbatma-navbat javob beradi.
- Barcha javoblar SQLite bazasida saqlanadi.
- Har bir Telegram foydalanuvchisi bitta so'rovnomani faqat bir marta topshira oladi.
- Admin natijalarda qatnashchilar soni, variantlar statistikasi va matnli javoblarni ko'radi.
- Oldingi bir savolli poll ovoz berish callbacklari ham saqlab qolindi.

O'RNATISH
1. ZIPni oching va ichidagi NextStep papkasini loyihangizdagi tegishli fayllar bilan solishtiring.
2. Ushbu yangilanishda o'zgargan fayllar:
   telegram_bot/database.py
   telegram_bot/states.py
   telegram_bot/keyboards.py
   telegram_bot/handlers/admin.py
   telegram_bot/handlers/polls.py
3. telegram_bot/main.py allaqachon polls.router ni import qilib, dp.include_routers(...) ichiga qo'shgan bo'lishi kerak. Ushbu arxivdagi main.py shu holatni tekshirish uchun ham mavjud.
4. .env faylingizni ZIPdan ko'chirmang; mavjud maxfiy kalitlaringizni o'zgartirmang.
5. Render'da mavjud Build/Start komandalarini o'zgartirish shart emas, agar hozirgi deploy shu loyihaning ishlayotgan konfiguratsiyasi bo'lsa.
6. O'zgarishlarni GitHub'ga yuboring va Render deploy tugashini kuting.

ADMIN
/admin -> Yangi so'rovnoma -> nom -> savol -> savol turi -> (variantli bo'lsa variantlarni har qatorda) -> yana savol yoki saqlash.
Natijalar: /admin -> So'rovnomalar -> kerakli so'rovnomani tanlash.

FOYDALANUVCHI
/sorovnomalar -> so'rovnomani tanlash -> savollarga javob berish.

ESLATMA
Bu ZIPda .env va bot tokenlari yo'q. SQLite ma'lumotlar bazangizni deploydan oldin zaxiralang. Render'dagi disk/persistent storage sozlamasi mavjud bazani saqlash uchun muhim.
