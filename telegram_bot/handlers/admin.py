import csv
import io

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from states import AdminEdit, AdminReply, Broadcast, NewQuiz, NewSurvey
import database as db
from config import OWNER_ID
from filters import PLAIN_TEXT, IsAdmin
from keyboards import (
    admin_panel,
    admins_kb,
    confirm_kb,
    finish_quiz_kb,
    quiz_list_kb,
    survey_list_kb,
    survey_type_kb,
    survey_continue_kb,
)
from services.broadcast import format_announcement, publish_announcement
from ui import LINE, esc, header

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

QUESTION_HELP = (
    "✍️ <b>Savolni yuboring</b>\n\n"
    "Format (to'g'ri javob oldiga <b>+</b> qo'ying):\n\n"
    "<code>Toshkent qaysi davlat poytaxti?\n"
    "+O'zbekiston\n"
    "Qozog'iston\n"
    "Qirg'iziston</code>\n\n"
    "2 tadan 8 tagacha variant bo'lishi mumkin. Savollar tugagach «Tugatish» tugmasini bosing."
)


def parse_question(text):
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not 3 <= len(lines) <= 9:
        return None
    options, correct = [], None
    for i, line in enumerate(lines[1:]):
        if line.startswith("+"):
            if correct is not None:
                return None
            correct = i
            line = line[1:].strip()
        options.append(line)
    if correct is None or not all(options):
        return None
    return {"text": lines[0], "options": options, "correct": correct}


async def panel_text():
    s = await db.stats()
    return (
        header("🛠", "Admin panel")
        + f"\n👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"📝 Quizlar: <b>{s['quizzes']}</b>\n"
        f"📢 E'lonlar: <b>{s['announcements']}</b>"
    )


@router.message(Command("admin"))
async def open_panel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        await panel_text(), reply_markup=admin_panel(message.from_user.id == OWNER_ID)
    )


@router.callback_query(F.data == "adm:back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        await panel_text(), reply_markup=admin_panel(call.from_user.id == OWNER_ID)
    )
    await call.answer()


# ---- statistika ----
@router.callback_query(F.data == "adm:stats")
async def stats(call: CallbackQuery):
    s = await db.stats()
    await call.message.answer(
        header("📊", "Statistika")
        + f"\n👥 Jami foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🆕 So'nggi 24 soatda qo'shilgan: <b>{s['new_24h']}</b>\n"
        f"🔥 So'nggi 24 soatda faol: <b>{s['active_24h']}</b>\n\n"
        f"📝 Quizlar: <b>{s['quizzes']}</b>\n"
        f"🎯 Yechilgan urinishlar: <b>{s['attempts']}</b>\n"
        f"📢 E'lonlar: <b>{s['announcements']}</b>"
    )
    await call.answer()


@router.callback_query(F.data == "adm:export")
async def export_results(call: CallbackQuery):
    rows = await db.export_results()
    if not rows:
        await call.answer("Hozircha natijalar yo'q", show_alert=True)
        return
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Ism", "Username", "Quiz", "Ball", "Jami", "Sana (UTC)"])
    for r in rows:
        writer.writerow(
            [r["full_name"], r["username"] or "", r["title"], r["score"], r["total"], r["finished_at"]]
        )
    
    data = buffer.getvalue().encode("utf-8-sig")
    await call.message.answer_document(
        BufferedInputFile(data, filename="natijalar.csv"),
        caption=f"📥 Barcha natijalar: {len(rows)} ta yozuv",
    )
    await call.answer()



@router.callback_query(F.data == "adm:new_quiz")
async def new_quiz(call: CallbackQuery, state: FSMContext):
    await state.set_state(NewQuiz.title)
    await call.message.answer("📝 Quiz nomini yozing:\n<i>Bekor qilish: /cancel</i>")
    await call.answer()


@router.message(NewQuiz.title, PLAIN_TEXT)
async def quiz_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip(), questions=[])
    await state.set_state(NewQuiz.questions)
    await message.answer(QUESTION_HELP)


@router.message(NewQuiz.questions, PLAIN_TEXT)
async def quiz_question(message: Message, state: FSMContext):
    question = parse_question(message.text)
    if not question:
        await message.answer("⚠️ Format noto'g'ri.\n\n" + QUESTION_HELP)
        return
    data = await state.get_data()
    questions = data["questions"] + [question]
    await state.update_data(questions=questions)
    await message.answer(
        f"✅ Savol qo'shildi (jami: <b>{len(questions)}</b>). Keyingisini yuboring yoki tugating.",
        reply_markup=finish_quiz_kb(),
    )


@router.callback_query(NewQuiz.questions, F.data == "adm:quiz_done")
async def quiz_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data["questions"]:
        await call.answer("Kamida bitta savol kerak", show_alert=True)
        return
    quiz_id = await db.create_quiz(data["title"], data["questions"])
    await state.clear()
    await call.message.answer(
        f"🎉 Quiz saqlandi!\n\n📝 <b>{esc(data['title'])}</b>\n"
        f"Savollar: <b>{len(data['questions'])}</b> · ID: <code>{quiz_id}</code>"
    )
    await call.answer()



@router.callback_query(F.data == "adm:del_quiz")
async def del_quiz_list(call: CallbackQuery):
    quizzes = await db.list_quizzes()
    if not quizzes:
        await call.answer("Quizlar yo'q", show_alert=True)
        return
    await call.message.answer(
        "🗑 Qaysi quiz o'chirilsin?",
        reply_markup=quiz_list_kb(quizzes, prefix="delq", show_done=False),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delq:"))
async def del_quiz_confirm(call: CallbackQuery):
    quiz_id = int(call.data.split(":")[1])
    quiz = await db.get_quiz(quiz_id)
    if not quiz:
        await call.answer("Quiz topilmadi", show_alert=True)
        return
    await call.message.edit_text(
        f"⚠️ <b>{esc(quiz['title'])}</b> o'chirilsinmi?\nUning barcha natijalari ham o'chadi.",
        reply_markup=confirm_kb(f"delok:{quiz_id}", "delno", yes_text="🗑 Ha, o'chirish"),
    )
    await call.answer()


@router.callback_query(F.data.startswith("delok:"))
async def del_quiz(call: CallbackQuery):
    await db.delete_quiz(int(call.data.split(":")[1]))
    await call.message.edit_text("🗑 Quiz o'chirildi.")
    await call.answer()


@router.callback_query(F.data == "delno")
async def del_quiz_cancel(call: CallbackQuery):
    await call.message.edit_text("✖️ Bekor qilindi.")
    await call.answer()



@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.text)
    await call.message.answer("📢 E'lon matnini yuboring:\n<i>Bekor qilish: /cancel</i>")
    await call.answer()


@router.message(Broadcast.text, PLAIN_TEXT)
async def broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(Broadcast.confirm)
    users = await db.count_users()
    await message.answer(
        "👁 <b>Ko'rinishi:</b>\n\n"
        + format_announcement("E'lon", message.text)
        + f"\n\n{LINE}\n<b>{users}</b> ta foydalanuvchiga yuborilsinmi?",
        reply_markup=confirm_kb("bc:yes", "bc:no", yes_text="🚀 Yuborish"),
    )


@router.callback_query(Broadcast.confirm, F.data == "bc:yes")
async def broadcast_send(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await call.message.edit_text("⏳ Yuborilmoqda...")
    await call.answer()
    await db.add_announcement("E'lon", data["text"])
    sent, failed = await publish_announcement(call.bot, "E'lon", data["text"])
    await call.message.answer(f"✅ Yuborildi: <b>{sent}</b>\nYetib bormadi: <b>{failed}</b>")


@router.callback_query(Broadcast.confirm, F.data == "bc:no")
async def broadcast_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("✖️ E'lon bekor qilindi.")
    await call.answer()



@router.callback_query(F.data.startswith("reply:"))
async def reply_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminReply.text)
    await state.update_data(target=int(call.data.split(":")[1]))
    await call.message.answer("↩️ Javobingizni yozing:\n<i>Bekor qilish: /cancel</i>")
    await call.answer()


@router.message(AdminReply.text, PLAIN_TEXT)
async def reply_send(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    try:
        await message.bot.send_message(
            data["target"], f"💬 <b>Admin javobi</b>\n{LINE}\n\n{esc(message.text)}"
        )
        await message.answer("✅ Javob yuborildi.")
    except TelegramAPIError:
        await message.answer("⚠️ Javobni yetkazib bo'lmadi (foydalanuvchi botni bloklagan bo'lishi mumkin).")



@router.callback_query(F.data == "adm:admins")
async def admins_menu(call: CallbackQuery):
    if call.from_user.id != OWNER_ID:
        await call.answer("Faqat bosh admin uchun", show_alert=True)
        return
    ids = await db.list_admins()
    text = header("👤", "Adminlar") + "\n" + "\n".join(
        f"• <code>{i}</code>{' 👑' if i == OWNER_ID else ''}" for i in ids
    )
    await call.message.edit_text(text, reply_markup=admins_kb())
    await call.answer()


@router.callback_query(F.data == "adm:add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID:
        await call.answer("Faqat bosh admin uchun", show_alert=True)
        return
    await state.set_state(AdminEdit.add_admin)
    await call.message.answer("Yangi adminning Telegram ID sini yuboring:\n<i>Bekor qilish: /cancel</i>")
    await call.answer()


@router.message(AdminEdit.add_admin, PLAIN_TEXT)
async def add_admin_save(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    if not message.text.strip().isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lishi kerak.")
        return
    await db.add_admin(int(message.text.strip()))
    await state.clear()
    await message.answer("✅ Admin qo'shildi.")


@router.callback_query(F.data == "adm:rm_admin")
async def rm_admin_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != OWNER_ID:
        await call.answer("Faqat bosh admin uchun", show_alert=True)
        return
    await state.set_state(AdminEdit.remove_admin)
    await call.message.answer("O'chiriladigan adminning ID sini yuboring:\n<i>Bekor qilish: /cancel</i>")
    await call.answer()


@router.message(AdminEdit.remove_admin, PLAIN_TEXT)
async def rm_admin_save(message: Message, state: FSMContext):
    if message.from_user.id != OWNER_ID:
        return
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lishi kerak.")
        return
    if int(text) == OWNER_ID:
        await message.answer("Bosh adminni o'chirib bo'lmaydi.")
        return
    await db.remove_admin(int(text))
    await state.clear()
    await message.answer("✅ Admin o'chirildi.")
# ========== KO'P SAVOLLI SO'ROVNOMA YARATISH ==========

async def ask_next_survey_question(message: Message, state: FSMContext):
    await state.set_state(NewSurvey.question)
    await message.answer(
        "✍️ Keyingi savol matnini yuboring.\n"
        "So'rovnomani bekor qilish: /cancel"
    )


@router.callback_query(F.data == "adm:new_survey")
async def new_survey_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(NewSurvey.title)
    await state.update_data(survey_questions=[])
    await call.message.answer("📋 Yangi so'rovnoma nomini yuboring:")
    await call.answer()


@router.message(NewSurvey.title, PLAIN_TEXT)
async def new_survey_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if not title:
        await message.answer("So'rovnoma nomi bo'sh bo'lmasin.")
        return
    await state.update_data(survey_title=title, survey_questions=[])
    await ask_next_survey_question(message, state)


@router.message(NewSurvey.question, PLAIN_TEXT)
async def new_survey_question(message: Message, state: FSMContext):
    question = message.text.strip()
    if not question:
        await message.answer("Savol matni bo'sh bo'lmasin.")
        return
    await state.update_data(pending_question=question)
    await state.set_state(NewSurvey.question_type)
    await message.answer(
        "Savol turini tanlang:",
        reply_markup=survey_type_kb()
    )


@router.callback_query(NewSurvey.question_type, F.data.startswith("svtype:"))
async def new_survey_question_type(call: CallbackQuery, state: FSMContext):
    kind = call.data.split(":", 1)[1]
    if kind not in ("choice", "text"):
        await call.answer("Noto'g'ri savol turi.", show_alert=True)
        return

    data = await state.get_data()
    questions = data.get("survey_questions", [])
    question = {"text": data["pending_question"], "type": kind, "options": []}

    if kind == "text":
        questions.append(question)
        await state.update_data(survey_questions=questions)
        await state.set_state(NewSurvey.continue_questions)
        await call.message.answer(
            f"✅ Matnli savol qo'shildi. Jami savollar: {len(questions)}",
            reply_markup=survey_continue_kb()
        )
    else:
        await state.update_data(pending_question_data=question)
        await state.set_state(NewSurvey.options)
        await call.message.answer(
            "Variantlarni har birini yangi qatordan yuboring. 2–8 ta variant:\n\n"
            "<code>Frontend\nBackend\nMobile</code>"
        )
    await call.answer()


@router.message(NewSurvey.options, PLAIN_TEXT)
async def new_survey_options(message: Message, state: FSMContext):
    options = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not 2 <= len(options) <= 8:
        await message.answer("⚠️ 2 tadan 8 tagacha variant yuboring.")
        return
    if len(set(options)) != len(options):
        await message.answer("⚠️ Bir xil variantlarni takrorlamang.")
        return

    data = await state.get_data()
    question = data.get("pending_question_data")
    if not question:
        await state.clear()
        await message.answer("Savol ma'lumoti topilmadi. Qaytadan boshlang.")
        return

    question["options"] = options
    questions = data.get("survey_questions", [])
    questions.append(question)
    await state.update_data(survey_questions=questions, pending_question_data=None)
    await state.set_state(NewSurvey.continue_questions)
    await message.answer(
        f"✅ Variantli savol qo'shildi. Jami savollar: {len(questions)}",
        reply_markup=survey_continue_kb()
    )


@router.callback_query(NewSurvey.continue_questions, F.data == "svcreate:add")
async def survey_add_question(call: CallbackQuery, state: FSMContext):
    await ask_next_survey_question(call.message, state)
    await call.answer()


@router.callback_query(NewSurvey.continue_questions, F.data == "svcreate:save")
async def survey_save(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    questions = data.get("survey_questions", [])
    if not questions:
        await call.answer("Kamida bitta savol qo'shing.", show_alert=True)
        return

    survey_id = await db.create_survey(data["survey_title"], questions)
    await state.clear()
    await call.message.answer(
        "🎉 <b>Ko'p savolli so'rovnoma yaratildi!</b>\n\n"
        f"📋 {esc(data['survey_title'])}\n"
        f"Savollar soni: <b>{len(questions)}</b>\n"
        f"ID: <code>{survey_id}</code>"
    )
    await call.answer("Saqlandi!")


@router.callback_query(F.data == "svcreate:cancel")
async def survey_create_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("So'rovnoma yaratish bekor qilindi.")
    await call.answer()


# ========== SO'ROVNOMA NATIJALARI ==========

@router.callback_query(F.data == "adm:surveys")
async def admin_survey_list(call: CallbackQuery):
    surveys = await db.list_surveys()
    if not surveys:
        await call.answer("So'rovnomalar mavjud emas.", show_alert=True)
        return
    await call.message.answer(
        "Natijasini ko'rmoqchi bo'lgan so'rovnomani tanlang:",
        reply_markup=survey_list_kb(surveys, "surveyres")
    )
    await call.answer()


@router.callback_query(F.data.startswith("surveyres:"))
async def admin_survey_result(call: CallbackQuery):
    try:
        survey_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri so'rovnoma.", show_alert=True)
        return

    result = await db.survey_results(survey_id)
    if not result:
        await call.answer("So'rovnoma topilmadi.", show_alert=True)
        return

    survey = result["survey"]
    lines = [
        f"📊 <b>{esc(survey['title'])}</b>",
        f"Jami qatnashganlar: <b>{result['total']}</b>",
        ""
    ]

    for index, question in enumerate(survey["questions"], start=1):
        lines.append(f"<b>{index}. {esc(question['text'])}</b>")
        answers = [
            response["answers"].get(str(question["id"]), "")
            for response in result["responses"]
        ]
        answers = [str(answer).strip() for answer in answers if str(answer).strip()]

        if question["type"] == "choice":
            for option in question["options"]:
                count = sum(1 for answer in answers if answer == option)
                percent = round(count * 100 / result["total"]) if result["total"] else 0
                lines.append(f"• {esc(option)} — <b>{count}</b> ({percent}%)")
        else:
            if answers:
                lines.append(f"Javoblar: <b>{len(answers)}</b>")
                for answer_no, answer in enumerate(answers[:20], start=1):
                    lines.append(f"{answer_no}) {esc(answer[:500])}")
                if len(answers) > 20:
                    lines.append(f"... yana {len(answers) - 20} ta javob")
            else:
                lines.append("Hozircha matnli javob yo'q.")
        lines.append("")

    text = "\n".join(lines)
    # Telegram xabar chegarasidan oshmasligi uchun bo'laklab yuborish
    for start in range(0, len(text), 3800):
        await call.message.answer(text[start:start + 3800])
    await call.answer()
