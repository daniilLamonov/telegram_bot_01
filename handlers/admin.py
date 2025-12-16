import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from database.repositories import ChatRepo, UserRepo
from filters.admin import IsAdminFilter

from utils.helpers import delete_message, temp_msg

router = Router(name="admin")

@router.message(Command("new"), IsAdminFilter())
async def cmd_new(message: Message):
    await delete_message(message)
    args = message.text.split()[1:]
    if not args:
        await temp_msg(message, "Использование: /new <процент>")
        return
    try:
        percent = float(args[0].replace(',', '.'))
        chat_id = message.chat.id

        is_set = await ChatRepo.set_commission(chat_id, percent)

        if not is_set:
            await temp_msg("Чат не инициализирован")

        await temp_msg(message, f"✅ Комиссия при обмене установлена: {percent:.2f}%\n".replace('.', ','))
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректный процент")


@router.message(Command("init"), IsAdminFilter())
async def cmd_init(message: Message):
    await delete_message(message)

    chat_info = await ChatRepo.get_chat(message.chat.id)

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

    success = await ChatRepo.initialize_chat(
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


@router.message(Command("reinit"), IsAdminFilter())
async def cmd_reinit(message: Message):
    await delete_message(message)
    chat_info = await ChatRepo.get_chat(message.chat.id)

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

    success = await ChatRepo.initialize_chat(
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


@router.message(Command("setadmin"))
async def cmd_setadmin(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    if not message.reply_to_message:
        await temp_msg(message, "⚠️ Ответьте на сообщение пользователя командой /setadmin")
        return

    target_user = message.reply_to_message.from_user

    if target_user.is_bot:
        await temp_msg(message, "❌ Нельзя назначить бота админом")
        return

    await UserRepo.set_admin(target_user.id, is_admin=True)

    await temp_msg(
        message,
        f"✅ Пользователь назначен администратором:\n"
        f"👤 ID: <code>{target_user.id}</code>\n"
        f"📝 Username: @{target_user.username or 'Не указан'}\n"
        f"📛 Имя: {target_user.first_name}",
        parse_mode="HTML"
    )


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    if not message.reply_to_message:
        await temp_msg(message, "⚠️ Ответьте на сообщение пользователя командой /removeadmin")
        return

    target_user = message.reply_to_message.from_user

    if target_user.id in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "Невозможно лишить прав суперадмина")
        return

    await UserRepo.set_admin(target_user.id, is_admin=False)

    await temp_msg(
        message,
        f"✅ Права администратора сняты:\n"
        f"👤 ID: <code>{target_user.id}</code>\n"
        f"📝 Username: @{target_user.username or 'Не указан'}",
        parse_mode="HTML"
    )
