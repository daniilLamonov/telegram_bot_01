from aiogram.fsm.context import FSMContext
from database.queries import initialize_chat, get_chat_info
from states import InitStates
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from database.queries import (
    set_commission,
)
from utils.helpers import delete_message, temp_msg

router = Router(name="admin")


@router.message(Command("new"))
async def cmd_new(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    args = message.text.split()[1:]
    if not args:
        await temp_msg(message, "Использование: /new <процент>")
        return
    try:
        percent = float(args[0])
        chat_id = message.chat.id

        await set_commission(chat_id, percent)

        await temp_msg(message, f"✅ Комиссия при пополнении установлена: {percent}%\n")
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректный процент")




@router.message(Command("init"))
async def cmd_init(message: Message, state: FSMContext):
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    chat_info = await get_chat_info(message.chat.id)
    if chat_info:
        await temp_msg(message,
            f"ℹ️ <b>Чат уже инициализирован</b>\n\n"
            f"📝 Контрагент: <b>{chat_info['contractor_name']}</b>\n"
            f"📅 Инициализирован: {chat_info['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Используйте /reinit для повторной инициализации",
            parse_mode="HTML"
        )
        return

    prompt_msg = await message.answer(
        "📝 <b>Инициализация чата</b>\n\n"
        "Введите название контрагента:",
        parse_mode="HTML"
    )

    await state.update_data(
        prompt_message_id=prompt_msg.message_id,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        chat_type=message.chat.type,
        admin_id=message.from_user.id
    )
    await state.set_state(InitStates.waiting_for_name)


@router.message(InitStates.waiting_for_name)
async def process_contractor_name(message: Message, state: FSMContext):
    contractor_name = message.text.strip()
    if not contractor_name:
        await temp_msg(message, "❌ Название не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    # try:
    #     await message.bot.delete_message(message.chat.id, data['prompt_message_id'])
    # except:
    #     pass
    chat_id = data['chat_id']
    chat_title = data['chat_title']
    chat_type = data['chat_type']
    admin_id = data['admin_id']

    success = await initialize_chat(
        chat_id=chat_id,
        chat_title=chat_title,
        chat_type=chat_type,
        contractor_name=contractor_name,
        initialized_by=admin_id
    )

    if success:
        await temp_msg(message,
            f"✅ <b>Чат успешно инициализирован!</b>\n\n"
            f"📝 Контрагент: <b>{contractor_name}</b>\n"
            f"🆔 Chat ID: <code>{chat_id}</code>\n\n"
            f"Теперь пользователи могут работать сботом в этом чате.",
            parse_mode="HTML"
        )
    else:
        await temp_msg(message, "❌ Ошибка при инициализации чата")

    await state.clear()


@router.message(Command("reinit"))
async def cmd_reinit(message: Message, state: FSMContext):
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    prompt_msg = await message.answer(
        "📝 <b>Изменение контрагента</b>\n\n"
        "Введите новое название:",
        parse_mode="HTML"
    )

    await state.update_data(
        prompt_message_id=prompt_msg.message_id,
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        chat_type=message.chat.type,
        admin_id=message.from_user.id
    )
    await state.set_state(InitStates.waiting_for_name)

