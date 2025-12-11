from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import settings
from database.queries import (
    get_balance,
    get_commission,
    get_contractor_name,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="common")


class InitStates(StatesGroup):
    waiting_for_name = State()



@router.message(Command("bal"))
async def cmd_bal(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    chat_id = message.chat.id
    balance_rub, balance_usdt = await get_balance(chat_id)
    commission = await get_commission(chat_id)
    contractor = await get_contractor_name(chat_id)

    await message.answer(
        (
            f'💰Баланс "{contractor}"\n'
            f"      {balance_rub:.2f} ₽\n"
            f"      {balance_usdt:.2f} $\n"
            f"      Комиссия: {commission}%"
        ),
        reply_markup=get_delete_keyboard(),
    )
