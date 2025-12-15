from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import settings
from database.repositories import UserRepo
from utils.helpers import temp_msg

router = Router()

@router.callback_query(F.data == "delete_message")
async def delete_message_callback(callback: CallbackQuery):
    # is_admin = await UserRepo.is_admin(callback.from_user.id)
    # if not is_admin:
    #     await temp_msg(callback.message, '❌ Эта возможность доступна только администраторам')
    #     await callback.answer()
    #     return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
