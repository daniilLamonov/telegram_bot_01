import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    InputMediaPhoto,
    Message,
)

from filters.admin import IsAdminFilter
from utils.generate_qr import (
    AuthenticationError,
    QRGenerationError,
    SiteUnavailableError,
    generate_qr,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard


router = Router(name="qr")


@router.message(Command("qr"), IsAdminFilter())
async def cmd_new(message: Message):
    await delete_message(message)

    args = message.text.split()[1:]

    if not args:
        await temp_msg(
            message,
            "Использование: /qr <сумма>",
        )
        return

    try:
        amount = float(args[0].replace(",", "."))

        if amount <= 0:
            raise ValueError

    except ValueError:
        await temp_msg(
            message,
            "❌ Некорректная сумма",
        )
        return

    # Сообщение-заглушка
    processing_msg = await message.answer(
        "⏳ QR-код в обработке..."
    )

    try:
        qr_bytes, data = await asyncio.to_thread(
            generate_qr,
            amount,
        )

    except SiteUnavailableError as e:
        await processing_msg.edit_text(
        f"❌ {e}",
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