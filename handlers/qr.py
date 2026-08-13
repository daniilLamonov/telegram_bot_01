import asyncio
import logging
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.repositories import QRSettingsRepo
from filters.admin import IsAdminFilter
from services.qr_queue import (
    CLEANUP_DELAY_MS,
    QRCleanupTask,
    QRJob,
    get_qr_queue,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard
from utils.permissions import is_super_admin


router = Router(name="qr")
logger = logging.getLogger(__name__)

MIN_QR_AMOUNT = 2_500
MAX_QR_AMOUNT = 150_000
LOCAL_CLEANUP_SECONDS = CLEANUP_DELAY_MS / 1000
_background_tasks: set[asyncio.Task] = set()

QR_MODES = {
    2: "СГБ",
    4: "РАЙФ",
    5: "РОСДОР",
    3: "КУБАНЬ",
}


async def reject_non_super_admin(message: Message) -> bool:
    if is_super_admin(message.from_user.id):
        return False
    await temp_msg(message, "❌ У вас нет прав для этой команды")
    return True


def schedule_local_cleanup(
    message: Message,
    message_ids: tuple[int, ...],
) -> None:
    task = asyncio.create_task(
        delete_messages_later(
            bot=message.bot,
            chat_id=message.chat.id,
            message_ids=message_ids,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def delete_messages_later(
    *,
    bot,
    chat_id: int,
    message_ids: tuple[int, ...],
) -> None:
    await asyncio.sleep(LOCAL_CLEANUP_SECONDS)
    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            logger.debug(
                "Не удалось удалить QR-сообщение chat_id=%s message_id=%s",
                chat_id,
                message_id,
                exc_info=True,
            )


async def schedule_cleanup(
    message: Message,
    message_ids: tuple[int, ...],
) -> None:
    try:
        await get_qr_queue().publish_cleanup(
            QRCleanupTask(
                chat_id=message.chat.id,
                message_ids=message_ids,
            )
        )
    except Exception:
        logger.exception("RabbitMQ cleanup недоступен, используется локальный таймер")
        schedule_local_cleanup(message, message_ids)


@router.message(Command("setqr"))
async def cmd_set_qr(message: Message):
    if await reject_non_super_admin(message):
        return

    await delete_message(message)

    builder = InlineKeyboardBuilder()
    for tab_index, name in QR_MODES.items():
        builder.button(
            text=name,
            callback_data=f"set_qr_mode:{tab_index}",
        )
    builder.adjust(2)

    await message.answer(
        "Выберите Р/С:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("set_qr_mode:"))
async def set_qr_mode(callback: CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        await callback.answer(
            "❌ У вас нет прав для этой команды",
            show_alert=True,
        )
        return

    try:
        tab_index = int(callback.data.split(":", 1)[1])
        mode_name = QR_MODES[tab_index]
    except (ValueError, KeyError):
        await callback.answer("❌ Некорректный режим", show_alert=True)
        return

    await QRSettingsRepo.set_tab_index(tab_index)
    await callback.message.edit_text(f"✅ Р/С выбран: {mode_name}")
    await callback.answer()


@router.message(Command("stopqr"))
async def cmd_stop_qr(message: Message):
    if await reject_non_super_admin(message):
        return

    await delete_message(message)
    await QRSettingsRepo.set_enabled(False)
    await temp_msg(message, "✅ Генерация QR выключена")


@router.message(Command("startqr"))
async def cmd_start_qr(message: Message):
    if await reject_non_super_admin(message):
        return

    await delete_message(message)
    await QRSettingsRepo.set_enabled(True)
    await temp_msg(message, "✅ Генерация QR включена")


@router.message(Command("qr"), IsAdminFilter())
async def cmd_new(message: Message):
    tab_index, is_enabled = await QRSettingsRepo.get_settings()
    if not is_enabled:
        await schedule_cleanup(message, (message.message_id,))
        await temp_msg(message, "Временно выключено")
        return

    args = message.text.split()[1:]

    if not args:
        await schedule_cleanup(message, (message.message_id,))
        await temp_msg(
            message,
            "Использование: /qr <сумма>",
        )
        return

    try:
        amount = int("".join(args).replace(",", "."))

    except ValueError:
        await schedule_cleanup(message, (message.message_id,))
        await temp_msg(
            message,
            "❌ Некорректная сумма",
        )
        return

    if not MIN_QR_AMOUNT <= amount <= MAX_QR_AMOUNT:
        await schedule_cleanup(message, (message.message_id,))
        await temp_msg(
            message,
            "❌ Сумма должна быть от 2 500 до 150 000",
        )
        return

    # Сообщение-заглушка
    processing_msg = await message.answer("⏳ QR-код в обработке...")

    job = QRJob(
        job_id=str(uuid4()),
        chat_id=message.chat.id,
        command_message_id=message.message_id,
        processing_message_id=processing_msg.message_id,
        amount=amount,
        tab_index=tab_index,
    )

    try:
        await get_qr_queue().publish_job(job)
    except Exception:
        logger.exception("Не удалось поставить QR в RabbitMQ")
        await processing_msg.edit_text(
            "❌ Очередь QR временно недоступна",
            reply_markup=get_delete_keyboard(),
        )
        schedule_local_cleanup(
            message,
            (message.message_id, processing_msg.message_id),
        )
        return
