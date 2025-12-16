from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database.repositories import ChatRepo
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
    balance_rub, balance_usdt = await ChatRepo.get_balance(chat_id)
    commission = await ChatRepo.get_commission(chat_id)
    contractor = await ChatRepo.get_contractor_name(chat_id)

    await message.answer(
        (
            f'Баланс "{contractor}"\n'
            f"{balance_rub:.2f} ₽\n"
            f"{balance_usdt:.2f} $\n"
            f"Комиссия: {commission}%"
        ).replace(".", ","),
        reply_markup=get_delete_keyboard(),
    )
