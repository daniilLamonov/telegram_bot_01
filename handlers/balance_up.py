import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.repositories import ChatRepo, OperationRepo, BalanceRepo
from filters.admin import IsAdminFilter
from utils.helpers import delete_message, temp_msg

router = Router(name="balance_up")

@router.message(Command("get"), IsAdminFilter())
async def cmd_get(message: Message):
    await delete_message(message)
    match = re.search(r"/get\s+([\d\s.,]+)", message.text)
    if not match:
        await temp_msg(message, "Использование: /get <сумма>")
        return

    try:
        amount_str = (
            match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount = float(amount_str)
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_id = await ChatRepo.get_balance_id(chat_id)

        balance_rub, balance_usdt = await BalanceRepo.get_by_id(balance_id)
        new_balance_rub = balance_rub + amount
        await BalanceRepo.update(balance_id, new_balance_rub, balance_usdt)

        await OperationRepo.log_operation(
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


@router.message(Command("gets"), IsAdminFilter())
async def cmd_gets(message: Message):
    await delete_message(message)

    match = re.search(r"/gets\s+([\d\s.,]+)", message.text)
    if not match.groups():
        await temp_msg(message, "Использование: /gets <сумма>")
        return

    try:
        amount_str = (
            match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount = float(amount_str)
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_id = await ChatRepo.get_balance_id(chat_id)

        balance_rub, balance_usdt = await BalanceRepo.get_by_id(balance_id)
        new_balance_usdt = balance_usdt + amount
        await BalanceRepo.update(balance_id, balance_rub, new_balance_usdt)

        await OperationRepo.log_operation(
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
