import asyncio

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.queries import (
    delete_operation_with_balance_correction,
    get_contractor_name,
    get_history,
    get_operation_details,
    set_commission,
)
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="admin")


@router.message(Command("new"))
async def cmd_new(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return
    args = message.text.split()[1:]
    if not args:
        await temp_msg(message, "Использование: /new <процент>")
        return
    try:
        percent = float(args[0])
        chat_id = message.chat.id

        await set_commission(chat_id, percent)

        await temp_msg(message, f"✅ Комиссия при пополнении установлена: {percent}%\n")
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректный процент")


@router.message(Command("history", "h"))
async def cmd_h(message: Message):
    await delete_message(message)
    chat_id = message.chat.id

    history = await get_history(chat_id)

    if not history:
        await temp_msg(message, "📜 История операций пуста")
        return

    contractor = await get_contractor_name(chat_id)
    msg = f"📜 Последние 10 операций\nКонтрагент: {contractor}\n\n"

    for op in history:
        msg += f'🔹 ID: {op["operation_id"]}\n'
        msg += f'Пользователь: @{op["username"]}\n'
        msg += f'Тип: {op["operation_type"]}\n'
        msg += f'Сумма: {float(op["amount"]):.2f} {op["currency"]}\n'
        if op["exchange_rate"]:
            msg += f'Курс: {float(op["exchange_rate"])}\n'
        msg += f'Время: {op["timestamp"]}\n'
        if op["description"]:
            msg += f'Описание: {op["description"]}\n'
        msg += "\n"

    await message.answer(msg, parse_mode="HTML", reply_markup=get_delete_keyboard())


@router.message(Command("delete", "del"))
async def cmd_delete(message: Message):
    await delete_message(message)
    if message.from_user.id not in settings.ADMIN_IDS:
        await temp_msg(message, "❌ Эта команда доступна только администраторам")
        return

    args = message.text.split()[1:]
    if not args:
        await temp_msg(
            message,
            "❌ Укажите ID операции\n"
            "Формат: /delete <operation_id>\n"
            "Пример: /delete a1b2c3d4",
            15,
        )
        return

    operation_id = args[0].strip()

    operation = await get_operation_details(operation_id)

    if not operation:
        await temp_msg(message, f"❌ Операция {operation_id} не найдена")
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Да, удалить", callback_data=f"confirm_delete:{operation_id}"
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"),
    )

    chat_info = f"Чат ID: {operation['chat_id']}" if operation.get("chat_id") else ""

    await message.answer(
        f"⚠️ Подтвердите удаление операции:\n\n"
        f'ID: {operation["operation_id"]}\n'
        f"{chat_info}\n"
        f'Тип: {operation["operation_type"]}\n'
        f'Сумма: {operation["amount"]:.2f} {operation["currency"]}\n'
        f'Время: {operation["timestamp"]}\n'
        f'Описание: {operation["description"]}\n\n'
        f"<b>Баланс чата будет автоматически скорректирован</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("confirm_delete:"))
async def process_delete_confirmation(callback: CallbackQuery):
    operation_id = callback.data.split(":")[1]

    operation = await get_operation_details(operation_id)

    if not operation:
        await callback.answer()
        await callback.message.edit_text("❌ Операция не найдена")
        await asyncio.sleep(15)
        try:
            await callback.message.delete()
        except Exception:
            pass

    operation_chat_id = operation["chat_id"]

    result = await delete_operation_with_balance_correction(
        operation_id, operation_chat_id
    )

    if result["success"]:
        await callback.message.edit_text(
            f"✅ Операция удалена успешно!\n\n"
            f"ID: {operation_id}\n"
            f"Чат ID: {operation_chat_id}\n"
            f'Тип: {result["operation"]["operation_type"]}\n'
            f'Сумма: {result["operation"]["amount"]:.2f} {result["operation"]["currency"]}\n\n'
            f"💰 Новый баланс чата:\n"
            f'₽: {result["new_balance"]["rub"]:.2f}\n'
            f'USDT: {result["new_balance"]["usdt"]:.2f}',
            parse_mode="HTML",
            reply_markup=get_delete_keyboard(),
        )
    else:
        await callback.message.edit_text(
            f'❌ Ошибка: {result["message"]}', parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "cancel_delete")
async def process_delete_cancel(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("❌ Удаление отменено")
    await asyncio.sleep(15)
    try:
        await callback.message.delete()
    except Exception:
        pass
