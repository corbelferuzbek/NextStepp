import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from aiohttp import web

import database as db
from config import BOT_TOKEN, BOT_PORT, SITE_API_KEY
from handlers import (
    admin,
    ai_chat,
    announcements,
    quiz,
    user,
    nextstep,
    polls,
)
from ui import BOT_NAME
from middlewares import SubscriptionMiddleware, ThrottleMiddleware
from services.api import create_app


COMMANDS = [
    BotCommand(command="start", description="Bosh menyu"),
    BotCommand(command="quizlar", description="Quizlar ro'yxati"),
    BotCommand(command="sorovnomalar", description="So'rovnomalar"),
    BotCommand(command="reyting", description="Eng yaxshi o'quvchilar"),
    BotCommand(command="profil", description="Mening natijalarim"),
    BotCommand(command="myid", description="Telegram ID ni ko'rish"),
    BotCommand(command="help", description="Bot haqida"),
    BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
]


# ------- Coder: Ozodovv ------- #

async def on_error(event: ErrorEvent):
    logging.exception(
        "Kutilmagan xatolik",
        exc_info=event.exception
    )

    update = event.update
    target = (
        update.message
        or (
            update.callback_query.message
            if update.callback_query
            else None
        )
    )

    if target:
        try:
            await target.answer(
                "⚠️ <b>Kutilmagan xatolik yuz berdi.</b>\n"
                "<i>Iltimos, qaytadan urinib ko'ring.</i>"
            )
        except Exception:
            pass

    return True


async def retry_network(func, *args, attempts=6, **kwargs):
    """
    Telegram bilan aloqa vaqtincha uzilsa,
    bir necha marta qayta urinadi.
    """

    for i in range(1, attempts + 1):
        try:
            return await func(*args, **kwargs)

        except TelegramNetworkError as e:
            if i == attempts:
                raise

            delay = min(2 * i, 15)

            logging.warning(
                "Telegram tarmoq xatosi (%s). "
                "%s soniyadan keyin qayta uriniladi (%s/%s)",
                e,
                delay,
                i,
                attempts
            )

            await asyncio.sleep(delay)


async def setup_profile(bot: Bot):
    """
    Bot menyusi va tavsifini o'rnatadi.
    Xatolik bo'lsa, bot ishga tushishiga xalaqit bermaydi.
    """

    try:
        await retry_network(
            bot.set_my_commands,
            COMMANDS
        )

        await retry_network(
            bot.set_my_short_description,
            f"{BOT_NAME} — IT o'rganuvchilar uchun quiz, e'lon va AI yordamchi"
        )

        await retry_network(
            bot.set_my_description,
            f"💻 {BOT_NAME} · IT ta'lim boti\n\n"
            "📝 Quizlar va reyting\n"
            "📊 So'rovnomalar\n"
            "📢 Musobaqa e'lonlari\n"
            "🤖 AI yordamchi\n"
            "✉️ Adminga murojaat\n\n"
            "Boshlash uchun START tugmasini bosing."
        )

    except Exception:
        logging.warning(
            "Bot profilini o'rnatib bo'lmadi",
            exc_info=True
        )


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN topilmadi. .env faylini tekshiring."
        )

    # Ma'lumotlar bazasini ishga tushirish
    await db.init_db()

    # Telegram bot
    session = AiohttpSession(timeout=90)

    bot = Bot(
        BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    # Dispatcher
    dp = Dispatcher()

    # Middleware
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(ThrottleMiddleware())
        observer.outer_middleware(SubscriptionMiddleware())

    # Global xatoliklarni boshqarish
    dp.errors.register(on_error)

    # Routerlarni ulash
    dp.include_routers(
        admin.router,
        user.router,
        quiz.router,
        polls.router,
        announcements.router,
        ai_chat.router,
        nextstep.router,
    )

    # Web API server
    runner = web.AppRunner(
        create_app(bot, SITE_API_KEY)
    )

    await runner.setup()

    await web.TCPSite(
        runner,
        "0.0.0.0",
        BOT_PORT
    ).start()

    logging.info(
        "Web API server %s-portda ishga tushdi.",
        BOT_PORT
    )

    try:
        # Eski webhookni o'chirish
        await retry_network(
            bot.delete_webhook,
            drop_pending_updates=True
        )

        # Bot profilini sozlash
        await setup_profile(bot)

        logging.info("NextStep Telegram bot ishga tushdi.")

        # Botni polling rejimida ishga tushirish
        await dp.start_polling(
            bot,
            polling_timeout=30
        )

    finally:
        logging.info("Bot to'xtatilmoqda...")

        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())