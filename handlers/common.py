from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import settings
from database.queries import (
    get_balance,
    get_commission,
    get_contractor_name,
    save_contractor_name,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="common")


class InitStates(StatesGroup):
    waiting_for_name = State()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await delete_message(message)
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Для начала работы:\n"
        "/init - инициализация чата\n"
        "/new - установить комиссию\n"
        "/help - помощь по командам"
    )


@router.message(Command("init"))
async def cmd_init(message: Message, state: FSMContext):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    prompt_msg = await message.answer("📝 Введите название контрагента:")
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(InitStates.waiting_for_name)


@router.message(InitStates.waiting_for_name)
async def process_contractor_name(message: Message, state: FSMContext):
    contractor_name = message.text.strip()
    data = await state.get_data()
    try:
        if "prompt_message_id" in data:
            await message.bot.delete_message(message.chat.id, data["prompt_message_id"])
        await message.delete()
    except Exception:
        pass
    if not contractor_name:
        error_msg = await message.answer(
            "❌ Название не может быть пустым. Попробуйте ещё раз:"
        )
        await state.update_data(prompt_message_id=error_msg.message_id)
        return
    await save_contractor_name(message.chat.id, contractor_name)
    await state.clear()

    await temp_msg(
        message,
        f'✅ <b>Контрагент установлен:</b>"{contractor_name}"',
        parse_mode="HTML",
    )


@router.message(Command("bal"))
async def cmd_bal(message: Message):
    await delete_message(message)
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
