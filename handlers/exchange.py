import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.repositories import ChatRepo, OperationRepo
from filters.admin import IsAdminFilter
from utils.helpers import delete_message, temp_msg

router = Router(name="exchange")


@router.message(Command("ch"), IsAdminFilter())
async def cmd_ch(message: Message):
    await delete_message(message)
    match = re.search(
        r'/ch\s+(\d+(?:\.\d+)?)\s+([\d\s.,]+)',
        message.text
    )
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Формат: <b>/ch курс сумма</b>\n\n"
            "Примеры:\n"
            "• /ch 95 5 000 000\n"
            "• /ch 95,5 1 000 000\n"
            "• /ch 100 500 000",
            parse_mode="HTML"
        )
        return

    try:
        rate = float(match.group(1).replace(',', '.'))

        amount_str = match.group(2).replace(' ', '').replace('\u00A0', '').replace(',', '.')
        amount_rub = float(amount_str)

        if rate <= 0 or amount_rub <= 0:
            await temp_msg(message, "❌ Курс и сумма должны быть > 0")
            return

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance_rub, balance_usdt = await ChatRepo.get_balance(chat_id)

        if balance_rub < amount_rub:
            await temp_msg(
                message,
                "❌ Недостаточно средств на балансе ₽\nБаланс чата: {balance_rub:.2f} ₽",
            )
            return
        amount_usdt = amount_rub / rate

        amount_after_commission, commission_amount = await calculate_commission(
            chat_id, amount_usdt, user_id, username
        )

        new_balance_rub = balance_rub - amount_rub
        new_balance_usdt = balance_usdt + amount_after_commission

        await ChatRepo.update_balance(chat_id, new_balance_rub, new_balance_usdt)

        await OperationRepo.log_operation(
            chat_id,
            user_id,
            username,
            "обмен_руб_на_usdt",
            amount_rub,
            "RUB",
            exchange_rate=rate,
            description=f"Получено: {amount_usdt:.2f} USDT",
        )

        await message.answer(
            (f"Обмен выполнен ✅\n\n"
            f"{amount_rub:.2f} ₽ списано \n"
            f"{rate} курс\n"
            f"{commission_amount:.2f}$ комиссия в чате ({rate}%)\n"
            f"{amount_after_commission:.2f}$ пополнен баланс").replace(".", ",")
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректные значения")


async def calculate_commission(chat_id, amount_usdt, user_id, username):
    commission = await ChatRepo.get_commission(chat_id)
    commission_amount = amount_usdt * (commission / 100)
    amount_after_commission = amount_usdt - commission_amount

    await OperationRepo.log_operation(
        chat_id,
        user_id,
        username,
        "комиссия",
        commission_amount,
        "USDT",
    )
    return amount_after_commission, commission_amount
