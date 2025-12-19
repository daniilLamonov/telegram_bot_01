import asyncio
import os
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import html_decoration as hd

from config import settings
from database.repositories import ChatRepo, OperationRepo
from filters.admin import IsAdminFilter
from states import CheckStates
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router()

FILES_DIR = settings.FILES_DIR
os.makedirs(FILES_DIR, exist_ok=True)


# ============= /check С ФОТО И ФИО =============


@router.message((F.photo | F.document) & F.caption & F.caption.contains("/check"))
async def cmd_check_with_photo(message: Message):
    await delete_message(message)
    text = message.caption.strip()

    match = re.search(r"/check\s+([\d\s.,]+)\s*(.*)$", text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Формат: <b>/check сумма ФИО</b>\n"
            "Пример: /check 5 000 Иванов Иван Иванович\n"
            "Или: /check 5 000 (если ФИО не указано)",
            parse_mode="HTML",
        )
        return

    try:
        amount_str = (
            match.group(1).strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount = float(amount_str)
        payer_info = match.group(2).strip() if match.group(2) else None

        if not payer_info or payer_info == "0":
            payer_info = "Не указано"

        if amount <= 0:
            await temp_msg(message, "❌ Сумма должна быть положительной")
            return

        await process_check_operation(message, amount, payer_info)

    except ValueError:
        await temp_msg(message, "❌ Неверный формат суммы. Используйте число.")
    except Exception as e:
        await temp_msg(message, f"❌ Ошибка при обработке чека: {e}")


# ============= /check БЕЗ ФОТО =============


@router.message(F.text & F.text.contains("/check"))
async def cmd_check_without_photo(message: Message, state: FSMContext):
    await delete_message(message)

    await state.set_state(CheckStates.waiting_for_file)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_all")

    bot_message = await message.answer(
        "📸 <b>Отправьте фото или документы чеков</b>\n\n"
        "Можете отправить несколько фото подряд.\n"
        "Я буду спрашивать про каждое по очереди.",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(
        queue=[],
        results_queue=[],
        processing=False,
        initial_msg_id=bot_message.message_id,
        waiting_for_more=False,
    )


@router.message(CheckStates.waiting_for_file, F.photo | F.document)
async def receive_file_after_check(message: Message, state: FSMContext):
    await add_to_queue(message, state)


# ============= ФОТО БЕЗ КОМАНДЫ =============


@router.message((F.photo | F.document) & ~F.caption)
async def handle_photo_without_command(message: Message, state: FSMContext):
    if message.caption and "/check" in message.caption:
        return

    await add_to_queue(message, state)


async def add_to_queue(message: Message, state: FSMContext):
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "фото"
        file_ext = "jpg"
    else:
        file_id = message.document.file_id
        file_type = "документ"
        file_ext = (
            message.document.file_name.split(".")[-1]
            if message.document.file_name
            else "file"
        )

    data = await state.get_data()
    queue = data.get("queue", [])
    processing = data.get("processing", False)
    waiting_for_more = data.get("waiting_for_more", False)

    queue.append(
        {
            "file_id": file_id,
            "file_type": file_type,
            "file_ext": file_ext,
            "msg_id": message.message_id,
            "user_id": message.from_user.id,  # ДОБАВЛЕНО
            "username": message.from_user.username or message.from_user.first_name,
        }
    )

    await state.update_data(queue=queue, last_file_time=datetime.now())
    await state.set_state(CheckStates.waiting_for_amount)

    if processing or waiting_for_more:
        return

    await state.update_data(waiting_for_more=True)
    asyncio.create_task(
        start_processing_after_delay(message.bot, message.chat.id, state)
    )


async def start_processing_after_delay(bot, chat_id, state: FSMContext):

    await asyncio.sleep(1)

    data = await state.get_data()

    try:
        initial_msg_id = data.get("initial_msg_id")
        if initial_msg_id:
            await bot.delete_message(chat_id, initial_msg_id)
    except Exception:
        pass

    await state.update_data(
        processing=True, waiting_for_more=False, initial_msg_id=None
    )

    queue = data.get("queue", [])

    if queue:
        sup_msg = await bot.send_message(
            chat_id=chat_id,
            text=f"📝 Получено файлов: {len(queue)}\n\nНачинаю обработку...",
        )
        processing_msg_id = sup_msg.message_id
        await state.update_data(processing_msg_id=processing_msg_id)
        await asyncio.sleep(1)

    await process_next_in_queue(bot, chat_id, state)


async def process_next_in_queue(bot, chat_id, state: FSMContext):
    data = await state.get_data()
    queue = data.get("queue", [])

    if not queue:
        await show_all_results(bot, chat_id, state)
        return
    current_file = queue[0]
    total_files = data.get("total_files", len(queue))
    current_number = total_files - len(queue) + 1

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Это не чек", callback_data="skip_current"),
        InlineKeyboardButton(text="Это не чеки", callback_data="cancel_all"),
    )
    username = current_file.get("username", "Неизвестно")
    caption_text = (
        f'📸 <b>{current_file["file_type"].capitalize()}</b> #{current_number} из {total_files}\n\n'
        f'👤 От: @{username}\n\n'
        f"💰 Напишите сумму и ФИО:\n"
        f"• <code>сумма ФИО</code>\n"
        f"• <code>сумма</code> (если ФИО не указано)\n\n"
        f"Пример: <code>5 000 Иванов Иван</code> или <code>5 000</code>"
    )

    try:
        if current_file["file_type"] == "фото":
            bot_msg = await bot.send_photo(
                chat_id=chat_id,
                photo=current_file["file_id"],
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
            )
        else:
            bot_msg = await bot.send_document(
                chat_id=chat_id,
                document=current_file["file_id"],
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
            )

        await state.update_data(
            current_bot_msg=bot_msg.message_id,
            current_file=current_file,
            total_files=total_files,
        )

    except Exception as e:
        print(f"Ошибка отправки: {e}")
        queue.pop(0)
        await state.update_data(queue=queue)
        await process_next_in_queue(bot, chat_id, state)


# ============= ПОЛУЧЕНИЕ ОТВЕТА =============


@router.message(CheckStates.waiting_for_amount, F.text)
async def receive_amount_and_payer(message: Message, state: FSMContext):
    await delete_message(message)

    text = message.text.strip()
    match = re.search(r"^([\d\s.,]+?)(?:\s+([а-яА-ЯёЁa-zA-Z\s]+))?$", text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Напишите:<code>сумма ФИО</code>\n"
            "Или просто:<code>сумма</code> (если ФИО не указано)\n"
            "Пример:<code>5 000 Иванов Иван</code> или <code>5 000</code>",
            parse_mode="HTML",
        )
        return
    try:
        amount_str = (
            match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount = float(amount_str)

        payer_info = match.group(2).strip() if match.group(2) else None

        if amount <= 0:
            await temp_msg(message, "❌ Сумма должна быть больше нуля!")
            return

        if not payer_info:
            payer_info = "Не указано"

        if amount <= 0:
            await temp_msg(message, "❌ Сумма должна быть положительной")
            return

        data = await state.get_data()
        current_file = data.get("current_file")
        current_bot_msg = data.get("current_bot_msg")

        if not current_file:
            await temp_msg(message, "❌ Ошибка: файл не найден")
            return
        try:
            await message.bot.delete_message(message.chat.id, current_file["msg_id"])
        except Exception:
            pass
        try:
            if current_bot_msg:
                await message.bot.delete_message(message.chat.id, current_bot_msg)
        except Exception:
            pass

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        file_id = current_file["file_id"]
        file_type = current_file["file_type"]
        file_ext = current_file["file_ext"]

        try:
            bot = message.bot
            file = await bot.get_file(file_id)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"check_{chat_id}_{timestamp}.{file_ext}"
            filepath = os.path.join(FILES_DIR, filename)

            await bot.download_file(file.file_path, filepath)

        except Exception as e:
            await temp_msg(message, f"❌ Ошибка при сохранении файла: {e}")
            queue = data.get("queue", [])
            if queue:
                queue.pop(0)
            await state.update_data(queue=queue)
            await process_next_in_queue(message.bot, chat_id, state)
            return

        await ChatRepo.add_to_balance(chat_id, amount)
        contractor_name = await ChatRepo.get_contractor_name(chat_id)

        op_id = await OperationRepo.log_operation(
            chat_id,
            user_id,
            username,
            "пополнение_руб_чек",
            amount,
            "RUB",
            description=f"Плательщик: {payer_info}. Зачислено: {amount:.2f} ₽. Тип: {file_type}. Файл: {filename}",
        )

        safe_payer = hd.quote(payer_info)
        safe_username = hd.quote(username)
        safe_contractor = hd.quote(contractor_name)

        results_queue = data.get("results_queue", [])
        results_queue.append(
            {
                "file_type": file_type,
                "op_id": op_id,
                "payer": safe_payer,
                "amount": amount,
                "username": safe_username,
                "contractor": safe_contractor,
            }
        )
        queue = data.get("queue", [])
        if queue:
            queue.pop(0)

        await state.update_data(queue=queue, results_queue=results_queue)
        await process_next_in_queue(message.bot, chat_id, state)
    except ValueError:
        await temp_msg(message, "❌ Неверный формат суммы")


async def show_all_results(bot, chat_id, state: FSMContext):
    data = await state.get_data()
    results_queue = data.get("results_queue", [])
    try:
        processing_msg_id = data.get("processing_msg_id")
        if processing_msg_id:
            await bot.delete_message(chat_id, processing_msg_id)
    except Exception:
        pass

    await state.clear()

    if not results_queue:
        return
    for result in results_queue:
        amount = result["amount"]
        if amount == int(amount):
            f_amount = f'{int(amount):,}'.replace(',', ' ')
        else:
            f_amount = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')
        builder = InlineKeyboardBuilder()
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f'✅ <b>Баланс пополнен</b> по чеку ({result["file_type"]})\n'
                f'ID:<code>{result["op_id"]}</code>\n'
                f'Плательщик: {result["payer"]}\n'
                f'Сумма: <b>{f_amount}</b> ₽\n'
                f'Внес: @{result["username"]}\n'
                f'КА: {result["contractor"]}\n\n'
                f'Для просмотра:<code>/hcheck {result["op_id"]}</code>'
            ).replace(".", ","),
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


# ============= КНОПКИ =============

@router.callback_query(F.data == "skip_current")
async def skip_current_file(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    try:
        current_bot_msg = data.get("current_bot_msg")
        if current_bot_msg:
            await callback.bot.delete_message(callback.message.chat.id, current_bot_msg)
    except Exception:
        pass

    # Переходим к следующему файлу
    queue = data.get("queue", [])
    if queue:
        queue.pop(0)
    await state.update_data(queue=queue)

    await process_next_in_queue(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data == "cancel_all")
async def cancel_all_files(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    messages_to_delete = [
        data.get("current_bot_msg"),
        data.get("processing_msg_id"),
        data.get("initial_msg_id"),
    ]

    for msg_id in messages_to_delete:
        if msg_id:
            try:
                await callback.bot.delete_message(callback.message.chat.id, msg_id)
            except Exception:
                pass

    await state.clear()


# ============= ОБРАБОТКА ОШИБОК =============


@router.message(CheckStates.waiting_for_file, F.text)
async def wrong_file_type(message: Message, state: FSMContext):
    await delete_message(message)
    await state.clear()
    await temp_msg(message, "❌ Ожидается фото или документ", parse_mode="HTML")


@router.message(CheckStates.waiting_for_amount, F.photo | F.document)
async def handle_extra_photo(message: Message, state: FSMContext):
    await add_to_queue(message, state)


# ============= ОБЩАЯ ФУНКЦИЯ =============


async def process_check_operation(message: Message, amount: float, payer_info: str):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    if message.photo:
        file_type = "фото"
        file_id = message.photo[-1].file_id
        file_ext = "jpg"
    else:
        file_type = "документ"
        file_id = message.document.file_id
        file_ext = (
            message.document.file_name.split(".")[-1]
            if message.document.file_name
            else "file"
        )

    try:
        bot = message.bot
        file = await bot.get_file(file_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"check_{chat_id}_{timestamp}.{file_ext}"
        filepath = os.path.join(FILES_DIR, filename)

        await bot.download_file(file.file_path, filepath)

    except Exception as e:
        await temp_msg(message, f"❌ Ошибка при сохранении файла: {e}")
        return

    await ChatRepo.add_to_balance(chat_id, amount)
    contractor_name = await ChatRepo.get_contractor_name(chat_id)

    op_id = await OperationRepo.log_operation(
        chat_id,
        user_id,
        username,
        "пополнение_руб_чек",
        amount,
        "RUB",
        description=f"Плательщик: {payer_info}. Зачислено: {amount:.2f} ₽. Тип: {file_type}. Файл: {filename}",
    )

    await delete_message(message)

    safe_payer = hd.quote(payer_info)
    safe_username = hd.quote(username)
    safe_contractor = hd.quote(contractor_name)
    if amount == int(amount):
        f_amount = f'{int(amount):,}'.replace(',', ' ')
    else:
        f_amount = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')
    builder = InlineKeyboardBuilder()
    await message.answer(
        f"✅<b>Баланс пополнен</b> по чеку ({file_type})\n"
        f"ID:<code>{op_id}</code>\n"
        f"Плательщик: {safe_payer}\n"
        f"Сумма: <b>{f_amount}</b> ₽\n"
        f"Внес: @{safe_username}\n"
        f"КА: {safe_contractor}\n\n"
        f"Для просмотра:<code>/hcheck {op_id}</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


# ============= ПРОСМОТР ЧЕКА =============


@router.message(Command("hcheck"))
async def cmd_history_check(message: Message):
    await delete_message(message)
    args = message.text.split()[1:]

    if not args:
        await temp_msg(message, "Использование: /hcheck <ID>\nПример: /hcheck 123456")
        return

    operation_id = args[0]
    operation = await OperationRepo.get_check(operation_id)

    if not operation:
        await temp_msg(message, "❌ Операция не найдена")
        return

    description = operation["description"]
    filename_match = re.search(r"Файл: (.+)$", description)

    if not filename_match:
        await temp_msg(message, "❌ Файл не найден")
        return

    filename = filename_match.group(1)
    filepath = os.path.join(FILES_DIR, filename)
    contractor_name = await ChatRepo.get_contractor_name(operation["chat_id"])

    safe_username = hd.quote(operation["username"])
    safe_contractor = hd.quote(contractor_name)
    amount = operation["amount"]
    if amount == int(amount):
        f_amount = f'{int(amount):,}'.replace(',', ' ')
    else:
        f_amount = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')

    operation_info = (
        f"📋 <b>Операция #{operation_id}</b>\n\n"
        f'Зачислено: <b>{f_amount} {operation["currency"]}</b>\n'
        f'Дата: {operation["timestamp"].strftime("%d.%m.%Y %H:%M")}\n'
        f"Внес: @{safe_username}\n"
        f"КА: {safe_contractor}"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_check:{operation_id}"),
        InlineKeyboardButton(text="Другая дата", callback_data=f"edit_date:{operation_id}"),
        InlineKeyboardButton(text="Скрыть", callback_data="delete_message")
    )
    if not os.path.exists(filepath):
        await message.answer(
            "❌ Файл/фото не найден на сервере\n" + operation_info,
            parse_mode="HTML",
            reply_markup=get_delete_keyboard(),
        )
        return

    from aiogram.types import FSInputFile

    if filename.endswith((".jpg", ".jpeg", ".png")):
        await message.answer_photo(
            photo=FSInputFile(filepath),
            caption=operation_info,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )
    else:
        await message.answer_document(
            document=FSInputFile(filepath),
            caption=operation_info,
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )


@router.message(Command("delete", "del"), IsAdminFilter())
async def cmd_delete(message: Message):
    await delete_message(message)
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

    operation = await OperationRepo.get_operation(operation_id)

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

    operation = await OperationRepo.get_operation(operation_id)

    if not operation:
        await callback.answer()
        await callback.message.edit_text("❌ Операция не найдена")
        await asyncio.sleep(15)
        try:
            await callback.message.delete()
        except Exception:
            pass
    operation_chat_id = operation["chat_id"]
    amount = operation["amount"]

    balance_rub, balance_usdt = await ChatRepo.get_balance(operation_chat_id)

    balance_rub = balance_rub - int(amount)

    result = await OperationRepo.delete_operation(operation_id)

    await ChatRepo.update_balance(operation_chat_id, balance_rub, balance_usdt)

    if result["success"]:
        await callback.message.edit_text(
            (
                f"✅ Операция удалена успешно!\n\n"
                f"ID: {operation_id}\n"
                f"Чат ID: {operation_chat_id}\n"
                f"Сумма: {amount:.2f}\n\n"
                f"Новый баланс чата:\n"
                f"₽: {balance_rub:.2f}\n"
                f"USDT: {balance_usdt:.2f}"
            ).replace(".", ","),
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

@router.callback_query(F.data.startswith("edit_check:"), IsAdminFilter())
async def start_edit_check(callback: CallbackQuery, state: FSMContext):
    operation_id = callback.data.split(":")[1]

    operation = await OperationRepo.get_check(operation_id)

    if not operation:
        await callback.answer("❌ Операция не найдена", show_alert=True)
        return

    description = operation["description"]
    current_amount = operation["amount"]

    payer_match = re.search(r"Плательщик: (.+?)\.", description)
    current_payer = payer_match.group(1) if payer_match else "Не указано"

    await state.set_state(CheckStates.editing_check)
    await state.update_data(
        editing_operation_id=operation_id,
        editing_chat_id=operation["chat_id"],
        old_amount=float(operation["amount"]),
        old_payer=current_payer,
        original_message_id=callback.message.message_id,
        original_message_text=callback.message.caption or callback.message.text,
    )

    if current_amount == int(current_amount):
        f_amount = f'{int(current_amount):,}'.replace(',', ' ')
    else:
        f_amount = f'{current_amount:,.2f}'.replace(',', ' ').replace('.', ',')

    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data="cancel_edit")

    edit_msg = await callback.message.answer(
        f"<b>Редактирование чека #{operation_id}</b>\n\n"
        f"Текущие данные:\n"
        f"💰 Сумма: <b>{f_amount}</b> ₽\n"
        f"👤 Плательщик: <b>{current_payer}</b>\n\n"
        f"Напишите новые данные в формате:\n"
        f"• <code>сумма ФИО</code>\n"
        f"• <code>сумма</code> (если ФИО не меняется)\n\n"
        f"Пример: <code>7 500 Петров Иван</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(edit_request_message_id=edit_msg.message_id)

    await callback.answer()


@router.message(CheckStates.editing_check, F.text)
async def process_edit_check(message: Message, state: FSMContext):
    await delete_message(message)

    text = message.text.strip()

    match = re.search(r"^([\d\s.,]+?)(?:\s+([а-яА-ЯёЁa-zA-Z\s]+))?$", text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Напишите: <code>сумма ФИО</code>\n"
            "Или просто: <code>сумма</code>\n"
            "Пример: <code>7 500 Петров Иван</code>",
            parse_mode="HTML",
        )
        return

    try:
        amount_str = match.group(1).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        new_amount = float(amount_str)

        if new_amount <= 0:
            await temp_msg(message, "❌ Сумма должна быть больше нуля!")
            return

        new_payer = match.group(2).strip() if match.group(2) else None

        data = await state.get_data()
        operation_id = data["editing_operation_id"]
        chat_id = data["editing_chat_id"]
        old_amount = float(data["old_amount"])
        old_payer = data["old_payer"]
        original_message_id = data.get("original_message_id")
        original_message_text = data.get("original_message_text")
        edit_request_message_id = data.get("edit_request_message_id")

        if not new_payer:
            new_payer = old_payer

        operation = await OperationRepo.get_check(operation_id)
        description = operation["description"]

        file_match = re.search(r"Файл: (.+)$", description)
        filename = file_match.group(1) if file_match else "unknown"

        type_match = re.search(r"Тип: (.+?)\.", description)
        file_type = type_match.group(1) if type_match else "фото"

        new_description = (
            f"Плательщик: {new_payer}. "
            f"Зачислено: {new_amount:.2f} ₽. "
            f"Тип: {file_type}. "
            f"Файл: {filename}"
        )

        balance_diff = new_amount - old_amount
        await ChatRepo.add_to_balance(chat_id, balance_diff)

        await OperationRepo.update_operation(
            operation_id,
            amount=new_amount,
            description=new_description
        )

        contractor_name = await ChatRepo.get_contractor_name(chat_id)
        username = operation["username"]

        if new_amount == int(new_amount):
            f_new = f'{int(new_amount):,}'.replace(',', ' ')
        else:
            f_new = f'{new_amount:,.2f}'.replace(',', ' ').replace('.', ',')

        if old_amount == int(old_amount):
            f_old = f'{int(old_amount):,}'.replace(',', ' ')
        else:
            f_old = f'{old_amount:,.2f}'.replace(',', ' ').replace('.', ',')

        try:
            if edit_request_message_id:
                await message.bot.delete_message(message.chat.id, edit_request_message_id)
        except Exception:
            pass

        try:
            if original_message_id:
                safe_username = hd.quote(username)
                safe_contractor = hd.quote(contractor_name)

                builder = InlineKeyboardBuilder()
                builder.button(text="Редактировать", callback_data=f"edit_check:{operation_id}")
                builder.button(text="Другая дата", callback_data=f"edit_date:{operation_id}")
                builder.button(text="Скрыть", callback_data="delete_message")

                new_text = (
                    f"📋 <b>Операция #{operation_id}</b>\n\n"
                    f"Зачислено: <b>{f_new} RUB</b>\n"
                    f"Дата: {operation['timestamp'].strftime('%d.%m.%Y %H:%M')}\n"
                    f"Внес: @{safe_username}\n"
                    f"КА: {safe_contractor}\n\n"
                    f"<i>✏️ Изменено: было {f_old} ₽, {old_payer}</i>"
                ).replace(".", ",")

                try:
                    await message.bot.edit_message_caption(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        caption=new_text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup(),
                    )
                except Exception:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        text=new_text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup(),
                    )
        except Exception as e:
            print(f"Не удалось отредактировать исходное сообщение: {e}")


    except ValueError:
        await temp_msg(message, "❌ Неверный формат суммы")
    except Exception as e:
        await temp_msg(message, f"❌ Ошибка при обновлении: {e}")
        await state.clear()


@router.callback_query(F.data == "cancel_edit", IsAdminFilter())
async def cancel_edit_check(callback: CallbackQuery, state: FSMContext):

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await callback.answer("❌ Редактирование отменено")



# ============= ИЗМЕНЕНИЕ ДАТЫ ЧЕКА =============

@router.callback_query(F.data.startswith("edit_date:"))
async def start_edit_date(callback: CallbackQuery, state: FSMContext):
    operation_id = callback.data.split(":")[1]

    operation = await OperationRepo.get_check(operation_id)

    if not operation:
        await callback.answer("❌ Операция не найдена", show_alert=True)
        return

    current_date = operation["timestamp"]

    await state.set_state(CheckStates.editing_date)
    await state.update_data(
        editing_operation_id=operation_id,
        editing_chat_id=operation["chat_id"],
        old_timestamp=current_date,
        original_message_id=callback.message.message_id,
        original_message_text=callback.message.caption or callback.message.text,
    )

    formatted_date = current_date.strftime("%d.%m.%Y %H:%M")

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_edit_date")

    edit_msg = await callback.message.answer(
        f"📅 <b>Изменение даты чека #{operation_id}</b>\n\n"
        f"Текущая дата: <b>{formatted_date}</b>\n\n"
        f"Введите новую дату:\n"
        f"• <code>ДД.ММ.ГГГГ</code> - время будет 00:00\n\n"
        f"Примеры:\n"
        f"<code>15.12.2025</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(edit_request_message_id=edit_msg.message_id)

    await callback.answer()


@router.message(CheckStates.editing_date, F.text)
async def process_edit_date(message: Message, state: FSMContext):
    await delete_message(message)

    text = message.text.strip()

    match = re.search(r"^(\d{2})\.(\d{2})\.(\d{4})$", text)

    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат даты!</b>\n\n"
            "Используйте:\n"
            "• <code>ДД.ММ.ГГГГ</code>\n\n"
            "Примеры:\n"
            "<code>15.12.2025</code>",
            parse_mode="HTML",
        )
        return

    try:
        day, month, year = match.groups()
        new_timestamp = datetime(
            int(year), int(month), int(day),
            0, 0
        )

        if new_timestamp > datetime.now():
            await temp_msg(
                message,
                "❌ Нельзя установить дату в будущем!"
            )
            return


        data = await state.get_data()
        operation_id = data["editing_operation_id"]
        chat_id = data["editing_chat_id"]
        old_timestamp = data["old_timestamp"]
        original_message_id = data.get("original_message_id")
        edit_request_message_id = data.get("edit_request_message_id")

        operation = await OperationRepo.get_check(operation_id)
        description = operation["description"]

        old_date_str = old_timestamp.strftime("%d.%m.%Y %H:%M")
        new_date_str = new_timestamp.strftime("%d.%m.%Y %H:%M")

        if "Дата изменена:" in description:
            description = re.sub(
                r"Дата изменена:.*?\.",
                f"Дата изменена: было {old_date_str}, стало {new_date_str}.",
                description
            )
        else:
            description = f" Дата изменена: было {old_date_str}, стало {new_date_str}." + description

        await OperationRepo.update_operation(
            operation_id,
            timestamp=new_timestamp,
            description=description
        )

        contractor_name = await ChatRepo.get_contractor_name(chat_id)
        username = operation["username"]
        amount = operation["amount"]

        if amount == int(amount):
            f_amount = f'{int(amount):,}'.replace(',', ' ')
        else:
            f_amount = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')

        payer_match = re.search(r"Плательщик: (.+?)\.", description)
        payer = payer_match.group(1) if payer_match else "Не указано"

        type_match = re.search(r"Тип: (.+?)\.", description)
        file_type = type_match.group(1) if type_match else "фото"

        try:
            if edit_request_message_id:
                await message.bot.delete_message(message.chat.id, edit_request_message_id)
        except Exception:
            pass

        try:
            if original_message_id:
                safe_payer = hd.quote(payer)
                safe_username = hd.quote(username)
                safe_contractor = hd.quote(contractor_name)

                builder = InlineKeyboardBuilder()
                builder.button(text="Редактировать", callback_data=f"edit_check:{operation_id}")
                builder.button(text="Другая дата", callback_data=f"edit_date:{operation_id}")
                builder.button(text="Скрыть", callback_data="delete_message")


                new_text = (
                    f"📋 <b>Операция #{operation_id}</b>\n\n"
                    f"Зачислено: <b>{f_amount} {operation['currency']}</b>\n"
                    f"Дата: {new_timestamp.strftime('%d.%m.%Y %H:%M')}\n"
                    f"Внес: @{safe_username}\n"
                    f"КА: {safe_contractor}\n\n"
                    f"<i>📅 Дата изменена: было {old_date_str}, стало {new_date_str}</i>"
                ).replace(".", ",")


                try:
                    await message.bot.edit_message_caption(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        caption=new_text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup(),
                    )
                except Exception:
                    await message.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=original_message_id,
                        text=new_text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup(),
                    )
        except Exception as e:
            print(f"Не удалось отредактировать исходное сообщение: {e}")

        await state.clear()

    except ValueError as e:
        await temp_msg(message, f"❌ Ошибка в дате: {e}\n\nПроверьте корректность введенной даты.")
    except Exception as e:
        await temp_msg(message, f"❌ Ошибка при обновлении: {e}")
        await state.clear()


@router.callback_query(F.data == "cancel_edit_date")
async def cancel_edit_date(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await callback.answer("❌ Изменение даты отменено")
