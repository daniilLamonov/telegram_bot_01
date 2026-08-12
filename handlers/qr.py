import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InputMediaPhoto,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.repositories import QRSettingsRepo
from filters.admin import IsAdminFilter
from utils.generate_qr import (
    AuthenticationError,
    QRGenerationError,
    SiteUnavailableError,
    generate_qr,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard
from utils.permissions import is_super_admin


router = Router(name="qr")

MIN_QR_AMOUNT = 2_500
MAX_QR_AMOUNT = 150_000

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
    # await delete_message(message)

    tab_index, is_enabled = await QRSettingsRepo.get_settings()
    if not is_enabled:
        await temp_msg(message, "Временно выключено")
        return

    args = message.text.split()[1:]

    if not args:
        await temp_msg(
            message,
            "Использование: /qr <сумма>",
        )
        return

    try:
        amount = int("".join(args).replace(",", "."))

    except ValueError:
        await temp_msg(
            message,
            "❌ Некорректная сумма",
        )
        return

    if not MIN_QR_AMOUNT <= amount <= MAX_QR_AMOUNT:
        await temp_msg(
            message,
            "❌ Сумма должна быть от 2 500 до 150 000",
        )
        return

    # Сообщение-заглушка
    processing_msg = await message.answer("⏳ QR-код в обработке...")

    try:
        qr_bytes, data = await asyncio.to_thread(
            generate_qr,
            amount,
            tab_index,
        )

    except SiteUnavailableError:
        await processing_msg.edit_text(
            "❌ Сайт агента недоступен",
            reply_markup=get_delete_keyboard(),
        )
        return

    except AuthenticationError:
        await processing_msg.edit_text(
            "❌ Не удалось авторизоваться у агента",
            reply_markup=get_delete_keyboard(),
        )
        return

    except QRGenerationError as e:
        await processing_msg.edit_text(
            f"❌ {e}",
            reply_markup=get_delete_keyboard(),
        )
        return

    except Exception:
        await processing_msg.edit_text(
            "❌ Произошла неизвестная ошибка",
            reply_markup=get_delete_keyboard(),
        )
        return

    # Превращаем байты в Telegram-файл
    photo = BufferedInputFile(
        qr_bytes,
        filename="qr.png",
    )

    # Редактируем "QR-код в обработке..."
    # прямо в сообщение с картинкой + подписью
    await processing_msg.edit_media(
        media=InputMediaPhoto(
            media=photo,
            caption=data,
        ),
        reply_markup=get_delete_keyboard(),
    )
