import re
from datetime import datetime, timedelta
import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database.repositories import ChatRepo, OperationRepo
from filters.admin import IsAdminFilter
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="exchange")

moscow_tz = pytz.timezone('Europe/Moscow')



@router.message(Command("ch"), IsAdminFilter())
async def cmd_ch(message: Message):
    await delete_message(message)
    match = re.search(r"/ch\s+(\d+(?:[.,]\d+)?)\s+([\d\s.,]+)", message.text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Формат: <b>/ch курс сумма</b>\n\n"
            "Примеры:\n"
            "• /ch 95 5 000 000\n"
            "• /ch 95,5 1 000 000\n"
            "• /ch 100 500 000",
            parse_mode="HTML",
        )
        return

    try:
        rate = float(match.group(1).replace(",", "."))

        amount_str = (
            match.group(2).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
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
        commission = await ChatRepo.get_commission(chat_id)
        amount_after_commission, commission_amount = await calculate_commission(
            chat_id, amount_usdt, user_id, username, commission
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
            (
                f"Обмен выполнен ✅\n\n"
                f"{amount_rub:.2f} ₽ списано \n"
                f"{rate} курс\n"
                f"{commission_amount:.2f}$ комиссия в чате ({commission}%)\n"
                f"{amount_after_commission:.2f}$ пополнен баланс"
            ).replace(".", ","),
            reply_markup=get_delete_keyboard(),
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректные значения")


@router.message(Command("chall"), IsAdminFilter())
async def cmd_chall(message: Message):
    await delete_message(message)
    match = re.search(r"/chall\s+(\d+(?:[.,]\d+)?)", message.text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Формат: <b>/chall курс</b>\n\n"
            "Пример:\n"
            "• /chall 90",
            parse_mode="HTML",
        )
        return
    try:
        rate = float(match.group(1).replace(",", "."))
        if rate <= 0:
            await temp_msg(message, "❌ Курс должен быть > 0")
            return
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name
        chats = await ChatRepo.get_all_chats()
        start_date = (datetime.now(moscow_tz).replace(tzinfo=None) - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # start_date = (datetime.now(moscow_tz).replace(tzinfo=None) - timedelta(days=0)).replace(
        #     hour=0, minute=0, second=0, microsecond=0
        # )
        end_date = start_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        report_lines = [f"<b>Массовый обмен по курсу: {rate}</b>\n"]
        report_lines.append(f"Период: {start_date.strftime('%d.%m.%Y')}\n")

        total_rub = 0
        total_usdt = 0
        total_commission = 0
        successful_chats = 0

        for chat in chats:
            chat_id = chat["chat_id"]
            contractor_name = await ChatRepo.get_contractor_name(chat_id)
            balance_rub = float(chat["balance_rub"])
            balance_usdt = float(chat["balance_usdt"])
            operations = await OperationRepo.get_checks_by_date(chat_id, start_date, end_date)
            amount_rub = float(sum(op["amount"] for op in operations))
            if amount_rub <= 0:
                report_lines.append(f"\n⚪️ Чат <code>{contractor_name}</code>: нет чеков за вчера")
                continue
            if balance_rub < amount_rub:
                report_lines.append(
                    f"\n❌ Чат <code>{contractor_name}</code>: недостаточно ₽\n"
                    f"   Нужно: {amount_rub:.2f} ₽\n"
                    f"   Есть: {balance_rub:.2f} ₽"
                )
                continue
            amount_usdt = amount_rub / rate
            commission = await ChatRepo.get_commission(chat_id)
            amount_after_commission, commission_amount = await calculate_commission(
                chat_id, amount_usdt, user_id, username, commission
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
            report_lines.append(
                f"\n✅ Чат <code>{contractor_name}</code>:\n"
                f"Чеков: {len(operations)}\n"
                f"Списано: {amount_rub:.2f} ₽\n"
                f"Получено: {amount_usdt:.2f} USDT\n"
                f"Комиссия: {commission_amount:.2f} USDT ({commission}%)\n"
                f"К балансу: {amount_after_commission:.2f} USDT"
            )
            total_rub += amount_rub
            total_usdt += amount_after_commission
            total_commission += commission_amount
            successful_chats += 1

        report_lines.append(
            f"\n\n📊 <b>Итого:</b>\n"
            f"✅ Обработано чатов: {successful_chats}\n"
            f"💸 Всего списано: {total_rub:.2f} ₽\n"
            f"💵 Всего получено: {total_usdt:.2f} USDT\n"
            f"💰 Всего комиссия: {total_commission:.2f} USDT"
        )
        report = "\n".join(report_lines).replace(".", ",")

        await message.answer(report, parse_mode="HTML", reply_markup=get_delete_keyboard())
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректные значения")


async def calculate_commission(chat_id, amount_usdt, user_id, username, commission):
    commission_amount = amount_usdt * (commission / 100)
    amount_after_commission = amount_usdt - commission_amount

    await OperationRepo.log_operation(
        chat_id,
        user_id,
        username,
        "комиссия",
        commission_amount,
        "USDT",
        description=f"Комиссия на момент обмена: {commission}%"
    )
    return amount_after_commission, commission_amount
