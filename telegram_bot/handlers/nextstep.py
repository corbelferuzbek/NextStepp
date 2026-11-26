from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import BTN_NEXTSTEP, main_menu, nextstep_menu, contest_list_kb
from services import nextstep as ns
from services.nextstep import NextStepError
from ui import esc, header

router = Router()

def _money(n):
    return f"{int(n):,}".replace(",", " ")

@router.message(F.text == BTN_NEXTSTEP)
async def nextstep_home(message: Message, state: FSMContext):
    await state.clear()
    try:
        contests = await ns.contests()
        await message.answer(
            header("🚀", "NextStep integratsiyasi") + "\n<blockquote>NextStep hisobingiz, coin hamyoningiz va musobaqalaringizni shu yerdan boshqaring.</blockquote>",
            reply_markup=nextstep_menu(contests),
        )
    except NextStepError as e:
        await message.answer(f"⚠️ {esc(str(e))}", reply_markup=main_menu())

@router.message(F.text == "/myid")
async def my_telegram_id(message: Message):
    await message.answer(f"Telegram ID: <code>{message.from_user.id}</code>\nBu ID ni NextStep saytidagi Profil → Telegram hisobini bog'lash bo'limiga kiriting.")

@router.callback_query(F.data == "ns:link")
async def link_help(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "🔗 <b>NextStep hisobini bog'lash</b>\n\n"
        "1. NextStep saytiga email va parol bilan kiring.\n"
        "2. Profil bo'limiga o'ting.\n"
        "3. Telegram ID maydoniga quyidagi ID ni kiriting.\n\n"
        f"<code>{call.from_user.id}</code>\n\n"
        "So'ng «Telegramni bog'lash» tugmasini bosing."
    )

@router.callback_query(F.data == "ns:wallet")
async def wallet(call: CallbackQuery):
    await call.answer()
    try:
        data = await ns.wallet(call.from_user.id)
        await call.message.answer(
            header("🪙", "NextStep coin hamyoni") + "\n"
            f"👤 <b>{esc(data['user']['name'])}</b>\n"
            f"💰 Balans: <b>{_money(data['coins'])} coin</b>\n"
            f"\n<i>Oxirgi 5 ta tranzaksiya:</i>\n" +
            ("\n".join(f"• {int(t['amount']):+} — {esc(t['reason'])}" for t in data.get('transactions', [])[:5]) or "Hozircha tranzaksiyalar yo'q." )
        )
    except NextStepError as e:
        await call.message.answer(f"⚠️ {esc(str(e))}")

@router.callback_query(F.data == "ns:history")
async def coin_history(call: CallbackQuery):
    await call.answer()
    try:
        txs = await ns.history(call.from_user.id)
        if not txs:
            text = "📜 <b>Coin tarixi</b>\n\nHozircha tranzaksiyalar yo'q."
        else:
            lines = [f"{'🟢' if int(t['amount']) >= 0 else '🔴'} <b>{int(t['amount']):+} coin</b> · balans: {t['balance_after']}\n<i>{esc(t['reason'])}</i>" for t in txs[:30]]
            text = header("📜", "Coin tranzaksiyalari") + "\n" + "\n\n".join(lines)
        await call.message.answer(text)
    except NextStepError as e:
        await call.message.answer(f"⚠️ {esc(str(e))}")

@router.callback_query(F.data == "ns:contests")
async def contest_list(call: CallbackQuery):
    await call.answer()
    try:
        rows = await ns.contests()
        text = header("🏁", "NextStep musobaqalari") + "\nKerakli musobaqani tanlang:"
        await call.message.answer(text, reply_markup=contest_list_kb(rows))
    except NextStepError as e:
        await call.message.answer(f"⚠️ {esc(str(e))}")

@router.callback_query(F.data.startswith("ns:join:"))
async def join_contest(call: CallbackQuery):
    await call.answer()
    try:
        contest_id = int(call.data.rsplit(":", 1)[1])
        data = await ns.register(call.from_user.id, contest_id)
        await call.message.answer(f"✅ <b>Ro'yxatdan o'tdingiz!</b>\n🏆 {esc(data.get('title', 'Musobaqa'))}\n\nMusobaqa topshirig'ini NextStep saytida bajarishingiz mumkin.")
    except (ValueError, NextStepError) as e:
        await call.message.answer(f"⚠️ {esc(str(e))}")
