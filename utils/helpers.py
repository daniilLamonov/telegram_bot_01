import asyncio
from aiogram.types import Message


async def temp_msg(message: Message,
                   text: str,
                   seconds: int = 10,
                   **kwargs):
    temp_msg = await message.answer(text, **kwargs)
    await asyncio.sleep(seconds)
    try:
        await temp_msg.delete()
    except Exception as e:
        print(e)
    return

async def delete_message(message: Message):
    try:
        await message.delete()
    except Exception as e:
        print(e)