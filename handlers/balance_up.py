from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from database.queries import get_balance, log_operation, update_balance
from utils.helpers import delete_message, temp_msg

router = Router(name="balance_up")


@router.message(Command("gets"))
async def cmd_gets(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    args = message.text.split()[1:]
    if not args:
        await temp_msg(message, "Использование: /gets <сумма>")
        return

    try:
        amount = float(args[0])
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_rub, balance_usdt = await get_balance(chat_id)
        new_balance_usdt = balance_usdt + amount
        await update_balance(chat_id, balance_rub, new_balance_usdt)

        await log_operation(
            chat_id,
            user_id,
            username,
            "пополнение_usdt",
            amount,
            "USDT",
            description=f"Зачислено: {amount:.2f} USDT",
        )

        await temp_msg(message, "✅ Баланс пополнен")
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректную сумму")


@router.message(Command("get"))
async def cmd_get(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    args = message.text.split()[1:]
    if not args:
        await temp_msg(message, "Использование: /get <сумма>")
        return

    try:
        amount = float(args[0])
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_rub, balance_usdt = await get_balance(chat_id)
        new_balance_rub = balance_rub + amount
        await update_balance(chat_id, new_balance_rub, balance_usdt)

        await log_operation(
            chat_id,
            user_id,
            username,
            "пополнение_руб",
            amount,
            "RUB",
            description=f" Зачислено: {amount:.2f} ₽",
        )

        await temp_msg(message, "✅ Баланс пополнен")
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректную сумму")
