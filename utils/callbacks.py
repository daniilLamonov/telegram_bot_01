from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import settings

router = Router()

@router.callback_query(F.data == "delete_message")
async def delete_message_callback(callback: CallbackQuery):
    is_admin = callback.from_user.id in settings.ADMIN_IDS
    if not is_admin:
        await callback.message.answer('❌ Эта возмоджность доступна только администраторам')
        await callback.answer()
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
