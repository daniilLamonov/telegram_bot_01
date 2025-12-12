import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from database.queries import get_balance, log_operation, update_balance
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="payments")


@router.message(Command("payr"))
async def cmd_payr(message: Message):
    await delete_message(message)

    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    match = re.search(
        r'/payr\s+([\d\s.,]+)',
        message.text
    )

    if not match:
        await temp_msg(message, "Использование: /payr <сумма>")
        return

    try:
        amount_str = match.group(1).replace(' ', '').replace('\u00A0', '').replace(',', '.')
        amount = float(amount_str)
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_rub, balance_usdt = await get_balance(chat_id)

        if balance_rub < amount:
            await temp_msg(
                message,(
                f"❌ Недостаточно средств\n"
                f"Требуется: {amount:,2f} ₽\n"
                f"Баланс чата: {balance_rub:,2f} ₽"
            ).replace('.', ','))
            return

        new_balance_rub = balance_rub - amount
        await update_balance(chat_id, new_balance_rub, balance_usdt)

        await log_operation(chat_id, user_id, username, "выплата_руб", amount, "RUB")

        await message.answer(
            f"Выплата {amount} ₽ выполнена\n" f"Баланс {new_balance_rub} ₽",
            reply_markup=get_delete_keyboard(),
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректную сумму")


@router.message(Command("pays"))
async def cmd_pays(message: Message):
    await delete_message(message)

    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    match = re.search(
        r'/pays\s+([\d\s.,]+)',
        message.text
    )

    if not match:
        await temp_msg(message, "Использование: /pays <сумма>")
        return

    try:
        amount_str = match.group(1).replace(' ', '').replace('\u00A0', '').replace(',', '.')
        amount = float(amount_str)
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_rub, balance_usdt = await get_balance(chat_id)

        if balance_usdt < amount:
            await temp_msg(
                message,(
                    f"❌ Недостаточно средств\n"
                    f"Требуется: {amount:,2f} USDT\n"
                    f"Баланс чата: {balance_usdt:,2f} USDT"
                    ).replace('.', ','))
            return

        new_balance_usdt = balance_usdt - amount
        await update_balance(chat_id, balance_rub, new_balance_usdt)

        await log_operation(chat_id, user_id, username, "выплата_usdt", amount, "USDT")

        await message.answer(
            f"Выплата {amount} USDT выполнена\n" f"Баланс {new_balance_usdt} USDT",
            reply_markup=get_delete_keyboard(),
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректную сумму")
