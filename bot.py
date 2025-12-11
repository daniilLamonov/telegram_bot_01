import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
# from middlewares.chat_init_check import ChatInitMiddleware
from config import settings
from database.connection import init_db, close_db
from handlers import (
    common_router,
    balance_up_router,
    payments_router,
    check_router,
    exchange_router,
    admin_router,
    help_router,
    export_router,
    callbacks_router,
    history_router,
)


async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="check", description="📸 Пополнить баланс по чеку"),
        # BotCommand(command="bal", description="💰 Текущий баланс"),
        # BotCommand(command="help", description="❓ Помощь"),
        BotCommand(command="/sv", description="📊 История операций"),
        # BotCommand(command="export", description="📑 Экспорт в Excel"),
    ]

    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # dp.message.middleware(ChatInitMiddleware())
    # dp.callback_query.middleware(ChatInitMiddleware())


    dp.include_router(callbacks_router)
    dp.include_router(admin_router)
    dp.include_router(check_router)
    dp.include_router(common_router)
    dp.include_router(balance_up_router)
    dp.include_router(payments_router)
    dp.include_router(exchange_router)
    dp.include_router(help_router)
    dp.include_router(export_router)
    dp.include_router(history_router)

    await set_bot_commands(bot)

    await init_db()
    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())



