from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.repositories import ChatRepo, UserRepo
from utils.helpers import temp_msg


class ChatInitMiddleware(BaseMiddleware):

    ADMIN_COMMANDS = {'init', 'help', 'start'}

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            chat_id = event.chat.id
            user_id = event.from_user.id
            chat_type = event.chat.type
            message = event
            is_admin_command = (
                    event.text and
                    event.text.startswith('/') and
                    event.text.split()[0][1:].split('@')[0] in self.ADMIN_COMMANDS
            )
        elif isinstance(event, CallbackQuery) and event.message:
            chat_id = event.message.chat.id
            user_id = event.from_user.id
            chat_type = event.message.chat.type
            message = event.message
            is_admin_command = False
        else:
            return await handler(event, data)

        is_admin = await UserRepo.is_admin(user_id)

        if chat_type == "private":
            await temp_msg(message,
                "🔒 <b>Доступ ограничен</b>\n\n"
                "Бот работает только в групповых чатах.",
                parse_mode="HTML"
            )
            return
        if is_admin and is_admin_command:
            return await handler(event, data)

        if not await ChatRepo.is_chat_initialized(chat_id):
            await temp_msg(message,
                "⚠️ <b>Чат не инициализирован</b>\n\n"
                "Администратор должен выполнить команду /init",
                parse_mode="HTML"
            )
            return

        return await handler(event, data)
