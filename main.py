import asyncio
from pytz import timezone

from config import logger
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from middlewares.chat_init_check import ChatInitMiddleware
from config import settings
from database.connection import init_db, close_db
from handlers import router
from middlewares.register_user import RegisterUserMiddleware
from middlewares.timeout_middleware import StateTimeoutMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.daily_report import generate_daily_report


async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="check", description="📸 Пополнить баланс по чеку"),
        BotCommand(command="/sv", description="📊 История операций"),
    ]

    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())



async def main():
    await init_db()

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(StateTimeoutMiddleware(timeout_seconds=60))
    dp.callback_query.middleware(StateTimeoutMiddleware(timeout_seconds=60))
    dp.message.middleware(RegisterUserMiddleware())
    dp.callback_query.middleware(RegisterUserMiddleware())
    dp.message.middleware(ChatInitMiddleware())
    dp.callback_query.middleware(ChatInitMiddleware())

    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone=timezone('Europe/Moscow'))

    scheduler.add_job(
        generate_daily_report,
        trigger=CronTrigger(hour=20, minute=00, timezone='Europe/Moscow'),
        kwargs={'bot': bot, 'chat_id': settings.REPORT_CHAT_ID}
    )

    async def print_hello(bot: Bot, chat_id: int):
        await bot.send_message(chat_id=chat_id, text='Hello from bot')

    scheduler.add_job(
        print_hello,
        trigger=CronTrigger(hour=23, minute=27, timezone='Europe/Moscow'),
        kwargs={'bot': bot, 'chat_id': settings.REPORT_CHAT_ID}
    )

    scheduler.start()

    await set_bot_commands(bot)
    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
