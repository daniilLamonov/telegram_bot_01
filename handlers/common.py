from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database.repositories import BalanceRepo
from filters.admin import IsAdminFilter

from utils.helpers import delete_message
from utils.keyboards import get_delete_keyboard

router = Router(name="common")


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

    await message.answer(
        (
            f'Баланс контрагента: "{contractor}"\n'
            f"{balance_rub:.2f} ₽\n"
            f"{balance_usdt:.2f} $\n"
            f"Комиссия: {commission:.2f}%"
        ).replace(".", ","),
        reply_markup=get_delete_keyboard(),
    )
