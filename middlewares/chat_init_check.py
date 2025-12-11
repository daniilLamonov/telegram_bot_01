from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, Message, CallbackQuery
from config import settings
from database.queries import is_chat_initialized
from states import InitStates


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

        state: FSMContext = data.get('state')
        is_admin = user_id in settings.ADMIN_IDS

        if chat_type == "private":
            await message.answer(
                "🔒 <b>Доступ ограничен</b>\n\n"
                "Бот работает только в групповых чатах.",
                parse_mode="HTML"
            )
            return

        if state:
            current_state = await state.get_state()
            if current_state == InitStates.waiting_for_name.state:
                return await handler(event, data)

        if is_admin and is_admin_command:
            return await handler(event, data)

        if not await is_chat_initialized(chat_id):
            await message.answer(
                "⚠️ <b>Чат не инициализирован</b>\n\n"
                "Администратор должен выполнить команду /init",
                parse_mode="HTML"
            )
            return

        return await handler(event, data)
