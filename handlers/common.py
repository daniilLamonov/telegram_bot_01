from datetime import datetime

import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database.repositories import BalanceRepo, OperationRepo, ChatRepo
from filters.admin import IsAdminFilter

from utils.helpers import delete_message, format_amount
from utils.keyboards import get_delete_keyboard

router = Router(name="common")

moscow_tz = pytz.timezone('Europe/Moscow')

class InitStates(StatesGroup):
    waiting_for_name = State()


@router.message(Command("bal"), IsAdminFilter())
async def cmd_bal(message: Message):
    await delete_message(message)
    chat_id = message.chat.id

    balance = await BalanceRepo.get_by_chat(chat_id)
    if not balance:
        await message.answer(
            "❌ Чат не инициализирован или баланс не найден",
            reply_markup=get_delete_keyboard(),
        )
        return

    contractor = balance["name"]
    balance_rub = float(balance["balance_rub"])
    balance_usdt = float(balance["balance_usdt"])
    commission = float(balance["commission_percent"] or 0)

    f_balance_rub = format_amount(balance_rub)
    f_balance_usdt = format_amount(balance_usdt)

    await message.answer(
        (
            f'Баланс контрагента: "{contractor}"\n'
            f"{f_balance_rub} ₽\n"
            f"{f_balance_usdt} $\n"
            f"Комиссия: {commission:.2f}%"
        ).replace(".", ","),
        reply_markup=get_delete_keyboard(),
    )

# balance now
@router.message(Command("nb"), IsAdminFilter())
async def cmd_nb(message: Message):
    await delete_message(message)
    chat_id = message.chat.id

    now = datetime.now(moscow_tz).replace(tzinfo=None)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    balance_id = await ChatRepo.get_balance_id(chat_id)

    if not balance_id:
        await message.answer(
            "❌ Чат не инициализирован или баланс не найден",
            reply_markup=get_delete_keyboard(),
        )
        return

    checks = await OperationRepo.get_checks_by_date(balance_id, start, now)

    if not checks:
        await message.answer(
            "📊 Сегодня не было операций по чекам",
            reply_markup=get_delete_keyboard()
        )
        return

    total_amount = sum(float(check['amount']) for check in checks)

    if total_amount == int(total_amount):
        formatted_amount = f'{int(total_amount):,}'.replace(',', ' ')
    else:
        formatted_amount = f'{total_amount:,.2f}'.replace(',', ' ').replace('.', ',')



    await message.answer(
        f"📊 <b>Статистика на сегодня</b>\n\n"
        f"📝 Чеков обработано: <b>{len(checks)}</b>\n"
        f"💰 Сумма чеков: <b>{formatted_amount}</b> ₽\n\n",
        parse_mode="HTML",
        reply_markup=get_delete_keyboard(),
    )
