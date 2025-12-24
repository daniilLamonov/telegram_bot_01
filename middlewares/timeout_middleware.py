import asyncio
from typing import Dict, Tuple, Callable, Awaitable, Any, List
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext


class StateTimeoutMiddleware(BaseMiddleware):
    """Очищает FSM + удаляет сообщения бота при таймауте"""

    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.active_timeouts: Dict[Tuple[int, int, int], asyncio.Task] = {}

    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        # Определяем идентификаторы
        if isinstance(event, Message):
            chat_id = event.chat.id
            user_id = event.from_user.id
            bot_id = event.bot.id
        elif isinstance(event, CallbackQuery):
            chat_id = event.message.chat.id
            user_id = event.from_user.id
            bot_id = event.bot.id
        else:
            return await handler(event, data)

        key = (bot_id, chat_id, user_id)

        # Отменяем предыдущий таймаут
        if key in self.active_timeouts:
            self.active_timeouts[key].cancel()
            del self.active_timeouts[key]

        # Выполняем handler
        result = await handler(event, data)

        # Проверяем состояние после обработки
        state: FSMContext = data.get('state')
        bot: Bot = data.get('bot')

        if state and bot:
            current_state = await state.get_state()
            if current_state:
                # Запускаем новый таймаут
                timeout_task = asyncio.create_task(
                    self._clear_state_after_timeout(key, state, bot, chat_id)
                )
                self.active_timeouts[key] = timeout_task

        return result

    async def _clear_state_after_timeout(
            self,
            key: Tuple[int, int, int],
            state: FSMContext,
            bot: Bot,
            chat_id: int
    ):
        """Очищает состояние и удаляет сообщения через заданное время"""
        try:
            await asyncio.sleep(self.timeout_seconds)

            # Проверяем, что состояние всё ещё активно
            current_state = await state.get_state()
            if not current_state:
                return

            # Получаем данные состояния
            data = await state.get_data()

            # Удаляем сообщения бота, если они были сохранены
            messages_to_delete = data.get('bot_messages_to_delete', [])
            for msg_id in messages_to_delete:
                try:
                    await bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass  # Сообщение уже удалено или недоступно

            # Удаляем файл/фото пользователя, если есть
            current_file = data.get('current_file', {})
            if current_file.get('msg_id'):
                try:
                    await bot.delete_message(chat_id, current_file['msg_id'])
                except Exception:
                    pass

            # Можно отправить уведомление об истечении времени
            # timeout_msg = await bot.send_message(
            #     chat_id,
            #     "⏰ Время ожидания истекло. Отправьте /check заново."
            # )
            # # Удаляем уведомление через 5 секунд
            # await asyncio.sleep(5)
            # try:
            #     await bot.delete_message(chat_id, timeout_msg.message_id)
            # except Exception:
            #     pass

            # Очищаем состояние
            await state.clear()

            # Удаляем таймаут
            if key in self.active_timeouts:
                del self.active_timeouts[key]

        except asyncio.CancelledError:
            pass  # Таймаут отменён (пользователь ответил)
        except Exception as e:
            print(f"Ошибка при очистке таймаута: {e}")
