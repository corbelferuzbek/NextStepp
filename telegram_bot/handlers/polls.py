from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

import database as db

from keyboards import (
    BTN_POLLS,
    poll_list_kb,
    poll_options_kb
)

from ui import esc, header

router = Router()


# ========== SO'ROVNOMALAR RO'YXATI ==========

@router.message(Command("sorovnomalar"))
@router.message(F.text == BTN_POLLS)
async def show_polls(message: Message):

    polls = await db.list_polls()

    if not polls:
        await message.answer(
            "📭 Hozircha so'rovnomalar mavjud emas."
        )
        return

    await message.answer(
        header("📊", "So'rovnomalar")
        + "\nOvoz bermoqchi bo'lgan so'rovnomani tanlang:",
        reply_markup=poll_list_kb(polls)
    )


# ========== SO'ROVNOMANI OCHISH ==========

@router.callback_query(F.data.startswith("poll:"))
async def open_poll(call: CallbackQuery):

    poll_id = int(call.data.split(":")[1])

    poll = await db.get_poll(poll_id)

    if not poll:
        await call.answer(
            "So'rovnoma topilmadi.",
            show_alert=True
        )
        return

    if await db.has_voted(poll_id, call.from_user.id):
        await call.answer(
            "Siz allaqachon ovoz bergansiz.",
            show_alert=True
        )
        return

    await call.message.answer(
        f"📊 <b>{esc(poll['title'])}</b>\n\n"
        f"<b>{esc(poll['question'])}</b>\n\n"
        "O'z variantingizni tanlang:",
        reply_markup=poll_options_kb(
            poll_id,
            poll["options"]
        )
    )

    await call.answer()


# ========== OVOZ BERISH ==========

@router.callback_query(F.data.startswith("vote:"))
async def vote(call: CallbackQuery):

    _, poll_id, option_index = call.data.split(":")

    poll_id = int(poll_id)
    option_index = int(option_index)

    poll = await db.get_poll(poll_id)

    if not poll:
        await call.answer(
            "So'rovnoma topilmadi.",
            show_alert=True
        )
        return

    if not 0 <= option_index < len(poll["options"]):
        await call.answer(
            "Variant topilmadi.",
            show_alert=True
        )
        return

    success = await db.cast_poll_vote(
        poll_id,
        call.from_user.id,
        option_index
    )

    if not success:
        await call.answer(
            "Siz allaqachon ovoz bergansiz.",
            show_alert=True
        )
        return

    await call.answer("Ovozingiz qabul qilindi!")

    results = await db.poll_results(poll_id)

    lines = [
        "✅ <b>Ovozingiz qabul qilindi!</b>",
        "",
        f"📊 <b>{esc(poll['title'])}</b>",
        ""
    ]

    for index, option in enumerate(poll["options"]):

        count = results["counts"][index]

        percentage = (
            round(count * 100 / results["total"])
            if results["total"]
            else 0
        )

        lines.append(
            f"{index + 1}. {esc(option)}"
            f" — {count} ta ({percentage}%)"
        )

    lines.append(
        f"\nJami ovoz: <b>{results['total']}</b>"
    )

    await call.message.edit_text(
        "\n".join(lines)
    )