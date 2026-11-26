# NextStep frontend

Frontend endi alohida fayllarga ajratilgan:
- `index.html` — sahifa tuzilishi
- `static/style.css` — dizayn va Markdown xabarlari stillari
- `static/i18n.js`, `static/data.js`, `static/script.js`, `static/admin.js`, `static/backend.js` — eski JavaScript qismlari asl yuklanish tartibida saqlangan.

AI javoblari `marked` orqali GitHub-Flavored Markdown formatida HTML ga aylantiriladi va `DOMPurify` orqali tozalanadi. Jadval, sarlavha, ro'yxat, havola, inline code va fenced code block qo'llab-quvvatlanadi.

Barcha mavjud backend endpointlari va login token oqimi saqlangan. API chaqiruvlari `/api/...` yo'llaridan foydalanadi.

**Eslatma:** ZIP ichiga `.env` va `.git` kiritilmadi. Maxfiy sozlamalarni Render Environment Variables orqali saqlang.
