import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.repositories import ChatRepo, OperationRepo, BalanceRepo
from filters.admin import IsAdminFilter
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="payments")


# @router.message(Command("payr"), IsAdminFilter())
# async def cmd_payr(message: Message):
#     await delete_message(message)
#
#     match = re.search(r"/payr\s+([\d\s.,]+)", message.text)
#
#     if not match:
#         await temp_msg(message, "Использование: /payr <сумма>")
#         return
#
#     try:
#         amount_str = (
#             match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
#         )
#         amount = float(amount_str)
#         chat_id = message.chat.id
#         user_id = message.from_user.id
#         username = message.from_user.username or message.from_user.first_name
#
#         balance_rub, balance_usdt = await ChatRepo.get_balance(chat_id)
#
#         if balance_rub < amount:
#             await temp_msg(
#                 message,
#                 (
#                     f"❌ Недостаточно средств\n"
#                     f"Требуется: {amount:.2f} ₽\n"
#                     f"Баланс чата: {balance_rub:.2f} ₽"
#                 ).replace(".", ","),
#             )
#             return
#
#         new_balance_rub = balance_rub - amount
#         await ChatRepo.update_balance(chat_id, new_balance_rub, balance_usdt)
#
#         await OperationRepo.log_operation(
#             chat_id, user_id, username, "выплата_руб", amount, "RUB"
#         )
#
#         await message.answer(
#             f"Выплата {amount:.2f} ₽ выполнена\n"
#             f"Баланс {new_balance_rub:.2f} ₽".replace(".", ","),
#             reply_markup=get_delete_keyboard(),
#         )
#     except (ValueError, IndexError):
#         await temp_msg(message, "Ошибка: введите корректную сумму")


@router.message(Command("pays"), IsAdminFilter())
async def cmd_pays(message: Message):
    await delete_message(message)

    match = re.search(r"/pays\s+([\d\s.,]+)", message.text)

    if not match:
        await temp_msg(message, "Использование: /pays <сумма>")
        return

    try:
        amount_str = (
            match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount = float(amount_str)
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance = await BalanceRepo.get_by_chat(chat_id)

        balance_rub, balance_usdt = float(balance["balance_rub"]), float(balance["balance_usdt"])
        if balance_usdt < amount:
            await temp_msg(
                message,
                (
                    f"❌ Недостаточно средств\n"
                    f"Требуется: {amount:.2f} USDT\n"
                    f"Баланс чата: {balance_usdt:.2f} USDT"
                ).replace(".", ","),
            )
            return

        balance_diff = balance_usdt - amount
        balance_id = balance["id"]

        await BalanceRepo.add(balance_id, 0, -amount)

        await OperationRepo.log_operation(
            balance_id, user_id, username, "выплата_usdt", amount, "USDT"
        )

        await message.answer(
            f"Выплата {amount:.2f} USDT выполнена\n"
            f"Баланс {balance_diff:.2f} USDT".replace(".", ","),
            reply_markup=get_delete_keyboard(),
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректную сумму")
