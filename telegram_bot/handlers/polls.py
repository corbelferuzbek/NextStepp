from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards import (
    BTN_POLLS,
    survey_list_kb,
    survey_question_options_kb,
)
from states import SurveyTaking
from ui import esc, header

router = Router()


async def send_survey_question(target, state: FSMContext, survey, index: int):
    questions = survey["questions"]

    if index >= len(questions):
        data = await state.get_data()
        saved = await db.save_survey_response(
            survey["id"],
            data["user_id"],
            data.get("answers", {})
        )
        await state.clear()

        if saved:
            await target.answer(
                "✅ <b>So'rovnoma yakunlandi!</b>\n"
                f"📋 <b>{esc(survey['title'])}</b>\n"
                "Barcha javoblaringiz saqlandi. Rahmat!"
            )
        else:
            await target.answer("Siz bu so'rovnomani avval to'ldirgansiz.")
        return

    question = questions[index]
    prefix = (
        f"📋 <b>{esc(survey['title'])}</b>\n"
        f"Savol {index + 1}/{len(questions)}\n\n"
        f"<b>{esc(question['text'])}</b>\n\n"
    )

    await state.update_data(
        current_index=index,
        current_question_id=question["id"]
    )

    if question["type"] == "text":
        await state.set_state(SurveyTaking.text_answer)
        await target.answer(prefix + "Javobingizni matn ko'rinishida yuboring:")
    else:
        await state.set_state(None)
        await target.answer(
            prefix + "Variantlardan birini tanlang:",
            reply_markup=survey_question_options_kb(
                survey["id"], index, question["options"]
            )
        )


@router.message(Command("sorovnomalar"))
@router.message(F.text == BTN_POLLS)
async def show_surveys(message: Message):
    surveys = await db.list_surveys(message.from_user.id)
    if not surveys:
        await message.answer("📭 Hozircha so'rovnomalar mavjud emas.")
        return
    await message.answer(
        header("📋", "So'rovnomalar")
        + "\nTo'ldirmoqchi bo'lgan so'rovnomani tanlang:",
        reply_markup=survey_list_kb(surveys)
    )


@router.callback_query(F.data.startswith("survey:"))
async def open_survey(call: CallbackQuery, state: FSMContext):
    try:
        survey_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri so'rovnoma.", show_alert=True)
        return

    survey = await db.get_survey(survey_id)
    if not survey or not survey["questions"]:
        await call.answer("So'rovnoma topilmadi.", show_alert=True)
        return

    if await db.has_completed_survey(survey_id, call.from_user.id):
        await call.answer("Siz bu so'rovnomani allaqachon to'ldirgansiz.", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        survey_id=survey_id,
        user_id=call.from_user.id,
        answers={}
    )
    await call.answer()
    await send_survey_question(call.message, state, survey, 0)


@router.callback_query(F.data.startswith("svans:"))
async def answer_choice(call: CallbackQuery, state: FSMContext):
    try:
        _, survey_id, index, option_index = call.data.split(":")
        survey_id, index, option_index = int(survey_id), int(index), int(option_index)
    except (ValueError, TypeError):
        await call.answer("Noto'g'ri javob.", show_alert=True)
        return

    data = await state.get_data()
    if data.get("survey_id") != survey_id or data.get("user_id") != call.from_user.id:
        await call.answer("So'rovnoma sessiyasi topilmadi. Qaytadan boshlang.", show_alert=True)
        return

    survey = await db.get_survey(survey_id)
    if not survey or not 0 <= index < len(survey["questions"]):
        await call.answer("Savol topilmadi.", show_alert=True)
        return

    question = survey["questions"][index]
    if question["type"] != "choice" or not 0 <= option_index < len(question["options"]):
        await call.answer("Variant topilmadi.", show_alert=True)
        return

    if data.get("current_index") != index:
        await call.answer("Bu savol allaqachon javoblangan.", show_alert=True)
        return

    answers = data.get("answers", {})
    answers[str(question["id"])] = question["options"][option_index]
    await state.update_data(answers=answers)
    await call.answer("Javob qabul qilindi.")
    await send_survey_question(call.message, state, survey, index + 1)


@router.message(SurveyTaking.text_answer)
async def answer_text(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("Iltimos, matnli javob yuboring.")
        return

    data = await state.get_data()
    survey_id = data.get("survey_id")
    survey = await db.get_survey(survey_id) if survey_id else None
    if not survey:
        await state.clear()
        await message.answer("So'rovnoma topilmadi. Qaytadan boshlang.")
        return

    index = data.get("current_index")
    if index is None or not 0 <= index < len(survey["questions"]):
        await state.clear()
        await message.answer("So'rovnoma sessiyasi yaroqsiz. Qaytadan boshlang.")
        return

    question = survey["questions"][index]
    if question["type"] != "text":
        await message.answer("Bu savol matnli javobni qabul qilmaydi.")
        return

    answers = data.get("answers", {})
    answers[str(question["id"])] = message.text.strip()[:3000]
    await state.update_data(answers=answers)
    await send_survey_question(message, state, survey, index + 1)

# Eski bir savolli poll yozuvlari bilan moslik: avval yaratilgan poll'lar ishlashda davom etadi.
from keyboards import poll_list_kb, poll_options_kb


@router.callback_query(F.data.startswith("poll:"))
async def open_legacy_poll(call: CallbackQuery):
    try:
        poll_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("Noto'g'ri so'rovnoma.", show_alert=True)
        return
    poll = await db.get_poll(poll_id)
    if not poll:
        await call.answer("So'rovnoma topilmadi.", show_alert=True)
        return
    if await db.has_voted(poll_id, call.from_user.id):
        await call.answer("Siz allaqachon ovoz bergansiz.", show_alert=True)
        return
    await call.message.answer(
        f"📊 <b>{esc(poll['title'])}</b>\n\n<b>{esc(poll['question'])}</b>\n\n"
        "O'z variantingizni tanlang:",
        reply_markup=poll_options_kb(poll_id, poll["options"])
    )
    await call.answer()


@router.callback_query(F.data.startswith("vote:"))
async def vote_legacy_poll(call: CallbackQuery):
    try:
        _, raw_poll_id, raw_option_index = call.data.split(":")
        poll_id, option_index = int(raw_poll_id), int(raw_option_index)
    except (ValueError, TypeError):
        await call.answer("Noto'g'ri javob.", show_alert=True)
        return
    poll = await db.get_poll(poll_id)
    if not poll or not 0 <= option_index < len(poll["options"]):
        await call.answer("Variant topilmadi.", show_alert=True)
        return
    success = await db.cast_poll_vote(poll_id, call.from_user.id, option_index)
    if not success:
        await call.answer("Siz allaqachon ovoz bergansiz.", show_alert=True)
        return
    results = await db.poll_results(poll_id)
    lines = ["✅ <b>Ovozingiz qabul qilindi!</b>", "", f"📊 <b>{esc(poll['title'])}</b>", ""]
    for i, option in enumerate(poll["options"]):
        count = results["counts"][i]
        percentage = round(count * 100 / results["total"]) if results["total"] else 0
        lines.append(f"• {esc(option)} — <b>{count}</b> ({percentage}%)")
    await call.message.answer("\n".join(lines))
    await call.answer("Ovozingiz qabul qilindi!")
