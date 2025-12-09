from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from config import settings
from database.queries import export_to_excel, get_contractor_name
from utils.dateparse import parse_date_period
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="export")


@router.message(Command("export"))
async def cmd_export(message: Message):
    await delete_message(message)
    chat_id = message.chat.id

    start_date, end_date, err = parse_date_period(message.text, "/export")
    if err:
        await temp_msg(message, err)
        return

    period_str = (
        f"{start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}"
        if start_date
        else "за всё время"
    )

    try:
        status_msg = await message.answer(f"📊 Генерирую отчет {period_str}...")

        buffer = await export_to_excel(
            chat_id=chat_id, start_date=start_date, end_date=end_date
        )
        contractor = await get_contractor_name(chat_id)

        filename = (
            f"report_{contractor}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        document = BufferedInputFile(buffer.read(), filename=filename)

        caption = f"📊 Отчет для чата: {contractor}\n📅 Период: {period_str}"
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer_document(
            document=document, caption=caption, reply_markup=get_delete_keyboard()
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при создании отчета: {e}")


@router.message(Command("exportall"))
async def cmd_export_all(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    start_date, end_date, err = parse_date_period(message.text, "/exportall")
    if err:
        await temp_msg(message, err)
        return

    period_str = (
        f"{start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}"
        if start_date
        else "за всё время"
    )

    try:
        status_msg = await message.answer(
            f"📊 Генерирую полный отчет {period_str}...\n⏳ Это может занять время..."
        )

        buffer = await export_to_excel(
            chat_id=None, start_date=start_date, end_date=end_date
        )

        filename = f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        document = BufferedInputFile(buffer.read(), filename=filename)

        caption = f"📊 Полный отчет по всем чатам и операциям\n📅 Период: {period_str}"
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer_document(
            document=document, caption=caption, reply_markup=get_delete_keyboard()
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при создании отчета: {e}")
