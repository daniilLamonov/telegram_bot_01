import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from middlewares.chat_init_check import ChatInitMiddleware
from config import settings
from database.connection import init_db, close_db
from handlers import router
from middlewares.register_user import RegisterUserMiddleware


async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="check", description="📸 Пополнить баланс по чеку"),
        BotCommand(command="/sv", description="📊 История операций"),
    ]

    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    print(settings.DATABASE_URL)

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(RegisterUserMiddleware())
    dp.callback_query.middleware(RegisterUserMiddleware())
    dp.message.middleware(ChatInitMiddleware())
    dp.callback_query.middleware(ChatInitMiddleware())

    dp.include_router(router)

    await set_bot_commands(bot)

    await init_db()
    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
