import re

from database.queries import initialize_chat, get_chat_info, set_commission
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings

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

        is_set = await set_commission(chat_id, percent)

        if not is_set:
            await temp_msg("Чат не инициализирован")

        await temp_msg(message, f"✅ Комиссия при пополнении установлена: {percent}%\n")
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректный процент")




@router.message(Command("init"))
async def cmd_init(message: Message):
    await delete_message(message)
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
    match = re.search(r'^/init(?:@\w+)?\s+(.+)', message.text)

    if not match:
        await temp_msg(
            message,
            "❌ Требуется ввести название КА.\n"
            "Пример: <code>/init ABC13 LTD</code>",
            parse_mode="HTML",
        )
        return
    contractor_name = match.group(1).strip()

    if not contractor_name:
        await temp_msg(message, """
        ❌ Требуется ввести команду с названием КА\n.
         Пример <code>/init ABC13 </code>
        """)
        return

    success = await initialize_chat(
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        chat_type=message.chat.type,
        contractor_name=contractor_name,
        initialized_by=message.from_user.id
    )

    if success:
        await temp_msg(message,
            f"✅ <b>Чат успешно инициализирован!</b>\n\n"
            f"📝 Контрагент: <b>{contractor_name}</b>\n"
            f"🆔 Chat ID: <code>{message.chat.id}</code>\n\n"
            f"Теперь пользователи могут работать с ботом в этом чате.",
            parse_mode="HTML"
        )
    else:
        await temp_msg(message, "❌ Ошибка при инициализации чата")


@router.message(Command("reinit"))
async def cmd_reinit(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    chat_info = await get_chat_info(message.chat.id)

    if not chat_info:
        await temp_msg(message,
                       f"ℹ️ <b>Чат еще не инициализирован</b>\n\n"
                       f"Используйте /init для инициализации",
                       parse_mode="HTML"
                       )
        return

    match = re.search(r'^/reinit(?:@\w+)?\s+(.+)', message.text)
    if not match:
        await temp_msg(
            message,
            "❌ Требуется ввести название КА.\n"
            "Пример: <code>/reinit ABC13 LTD</code>",
            parse_mode="HTML",
        )
        return
    contractor_name = match.group(1).strip()

    success = await initialize_chat(
        chat_id=message.chat.id,
        chat_title=message.chat.title,
        chat_type=message.chat.type,
        contractor_name=contractor_name,
        initialized_by=message.from_user.id
    )

    if success:
        await temp_msg(message,
                       f"✅ <b>Чат успешно инициализирован!</b>\n\n"
                       f"📝 Контрагент: <b>{contractor_name}</b>\n"
                       f"🆔 Chat ID: <code>{message.chat.id}</code>\n\n"
                       f"Теперь пользователи могут работать с ботом в этом чате.",
                       parse_mode="HTML"
                       )
    else:
        await temp_msg(message, "❌ Ошибка при инициализации чата")

