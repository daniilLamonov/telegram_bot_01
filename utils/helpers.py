import asyncio
import logging
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def temp_msg(message: Message, text: str, seconds: int = 10, **kwargs):
    temp_msg = await message.answer(text, **kwargs)
    await asyncio.sleep(seconds)
    try:
        await temp_msg.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить временное сообщение: {e}")


async def delete_message(message: Message):
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")
