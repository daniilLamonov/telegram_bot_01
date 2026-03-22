import asyncio
import re
from datetime import datetime, timedelta, timezone
import pandas as pd
from io import BytesIO

from decimal import Decimal, InvalidOperation
from collections import Counter

import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings, logger
from database.repositories import ChatRepo, OperationRepo, BalanceRepo
from filters.admin import IsAdminFilter
from states import CompareStates
from utils.daily_report import generate_daily_report
from utils.excel import export_to_excel, export_comparison_report, export_comparison_report_exl
from utils.dateparse import parse_date_period
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="export")
moscow_tz = pytz.timezone('Europe/Moscow')
SUPER_ADMIN_ID = settings.SUPER_ADMIN_ID


@router.message(Command("export"), IsAdminFilter())
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
        balance_id = await ChatRepo.get_balance_id(chat_id)

        contractor = await BalanceRepo.get_contractor_name(balance_id)

        filename = (
            f"report_{contractor}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        document = BufferedInputFile(buffer.read(), filename=filename)

        caption = f"📊 Отчет для КА: {contractor}\n📅 Период: {period_str}"
        try:
            await status_msg.delete()
        except Exception:
            pass
        await message.answer_document(
            document=document, caption=caption, reply_markup=get_delete_keyboard()
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при создании отчета: {e}")


@router.message(Command("exportall"), IsAdminFilter())
async def cmd_export_all(message: Message):
    if message.from_user.id not in SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    await delete_message(message)
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



@router.message(Command("compare_exl"), IsAdminFilter())
async def cmd_compare_excel(message: Message, state: FSMContext):
    await delete_message(message)

    if message.from_user.id not in SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав")
        return

    date_match = re.search(r'/compare_exl\s+(\d{2}\.\d{2}\.\d{4})', message.text)

    if date_match:
        try:
            target_date = datetime.strptime(date_match.group(1), "%d.%m.%Y")
        except ValueError:
            await temp_msg(message, "❌ Формат даты: ДД.ММ.ГГГГ")
            return
    else:
        target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start_date = target_date
    end_date = start_date + timedelta(days=1)

    await state.set_state(CompareStates.waiting_for_excel_file)

    msg = await message.answer(
        f"<b>Сравнение Excel c БД </b>\n"
        f"Дата: {target_date.strftime('%d.%m.%Y')}\n\n"
        "Пришлите Excel файл (.xlsx)",
        parse_mode="HTML"
    )

    await state.update_data(
        start_date=start_date,
        end_date=end_date,
        target_date=target_date,
        initial_msg_id=msg.message_id,
    )


@router.message(CompareStates.waiting_for_excel_file)
async def receive_excel_file(message: Message, state: FSMContext):
    data = await state.get_data()
    target_date = data["target_date"].date()
    initial_msg_id = data["initial_msg_id"]

    try:
        await message.bot.delete_message(message.chat.id, initial_msg_id)
    except:
        pass

    if not message.document or not message.document.file_name.lower().endswith((".xlsx", ".xls")):
        err_message = await message.answer("Нужен Excel файл (.xlsx)")
        await state.clear()
        await asyncio.sleep(3)
        await err_message.delete()
        await delete_message(message)
        return

    processing_msg = await message.answer("Обрабатываю файл...")

    try:
        file = await message.bot.get_file(message.document.file_id)
        buffer = BytesIO()
        await message.bot.download_file(file.file_path, buffer)
        await delete_message(message)

        df = pd.read_excel(buffer)

        if df.empty:
            await processing_msg.edit_text("Пустой файл")
            await state.clear()
            return

        df.columns = [str(col).strip().lower() for col in df.columns]

        REQUIRED_COLUMNS = {
            "date": ["дата и время регистрации заказа"],
            "order_id": ["номер заказа"],
            "status": ["статус заказа"],
            "amount": ["сумма заказа"],
        }

        def find_column(names):
            for col in df.columns:
                if col in names:
                    return col
            return None

        col_map = {k: find_column(v) for k, v in REQUIRED_COLUMNS.items()}

        if not all(col_map.values()):
            await processing_msg.edit_text("Не найдены нужные колонки")
            await state.clear()
            return

        def parse_amount(val):
            try:
                val = str(val).replace(" ", "").replace(",", ".").replace("₽", "")
                return Decimal(val)
            except (InvalidOperation, ValueError):
                return None

        file_operations = []
        seen = set()

        for i, row in df.iterrows():
            try:
                if "дата и время" in str(row[col_map["date"]]).lower():
                    continue

                status = str(row[col_map["status"]]).strip().casefold()
                if status != "captured":
                    continue

                date_val = pd.to_datetime(row[col_map["date"]], errors="coerce")
                if pd.isna(date_val) or date_val.date() != target_date:
                    continue

                amount = parse_amount(row[col_map["amount"]])
                if not amount or amount <= 0:
                    continue

                order_id = str(row[col_map["order_id"]]).strip()

                key = (order_id, amount)
                if key in seen:
                    continue
                seen.add(key)

                file_operations.append({
                    "transaction_id": order_id,
                    "amount": amount,
                    "datetime": date_val
                })

            except Exception as e:
                logger.warning(f"Row {i} skipped: {e}")
                continue

        if not file_operations:
            await processing_msg.edit_text("Нет успешных операций за эту дату")
            await state.clear()
            return

        db_operations_raw = await OperationRepo.get_all_checks_by_date(
            data["start_date"],
            data["end_date"]
        )

        file_amounts = Counter([op['amount'] for op in file_operations])
        db_amounts = Counter([Decimal(str(op['amount'])) for op in db_operations_raw])

        only_in_file = []
        only_in_db = []
        matched_operations = []

        # Только в файле (красный)
        for amount, file_count in file_amounts.items():
            db_count = db_amounts.get(amount, 0)
            if file_count > db_count:
                diff = file_count - db_count
                matching_ops = [op for op in file_operations if op['amount'] == amount]
                only_in_file.extend(matching_ops[:diff])

        # Только в БД (желтый)
        for amount, db_count in db_amounts.items():
            file_count = file_amounts.get(amount, 0)
            if db_count > file_count:
                diff = db_count - file_count
                matching_ops = [
                    op for op in db_operations_raw
                    if Decimal(str(op['amount'])) == amount
                ]
                only_in_db.extend(matching_ops[:diff])

        # СОВПАВШИЕ (зеленый)
        for amount, file_count in file_amounts.items():
            db_count = db_amounts.get(amount, 0)
            match_count = min(file_count, db_count)
            matching_file_ops = [op for op in file_operations if op['amount'] == amount][:match_count]
            matched_operations.extend(matching_file_ops)

        if not only_in_file and not only_in_db:
            total_file = sum(op['amount'] for op in file_operations)
            total_db = sum(Decimal(str(op['amount'])) for op in db_operations_raw)

            await processing_msg.edit_text(
                f"Все успешные операции совпали!\n\n"
                f"Excel: {len(file_operations)}\n"
                f"БД: {len(db_operations_raw)}\n"
                f"Сумма Excel: {total_file:,.2f}\n"
                f"Сумма БД: {total_db:,.2f}",
                parse_mode="HTML",
                reply_markup=get_delete_keyboard()
            )
            await state.clear()
            return

        await processing_msg.edit_text("Найдены расхождения, формирую отчет...")

        total_file = sum(op['amount'] for op in file_operations)
        total_db = sum(Decimal(str(op['amount'])) for op in db_operations_raw)
        total_file_count = sum(file_amounts.values())

        matched_count = sum(min(file_amounts[a], db_amounts.get(a, 0)) for a in file_amounts)
        not_matched_count = total_file_count - matched_count
        matched_amount = sum(a * min(file_amounts[a], db_amounts.get(a, 0)) for a in file_amounts)

        buffer = await export_comparison_report_exl(
            only_in_file=only_in_file,
            only_in_db=only_in_db,
            matched_operations=matched_operations
        )

        await message.answer_document(
            BufferedInputFile(
                buffer.read(),
                filename=f"compare_excel_{data['target_date'].strftime('%Y%m%d')}.xlsx"
            ),
            caption=(
                f"РАСХОЖДЕНИЯ\n\n"
                f"🔴Красным: есть в файле, нет в БД: {len(only_in_file)} шт.\n"
                f"🟡Желтым: есть в БД, нет в файле: {len(only_in_db)} шт.\n\n"
                f"Дата: {data['target_date'].strftime('%d.%m.%Y')}\n\n"
                f"Общая сумма схождений: {matched_amount:,.2f} ₽\n"
                f"Кол-во чеков сошлось: {matched_count}\n"
                f"Кол-во чеков НЕ сошлось (из файла): {not_matched_count}\n\n"
                f"Общая сумма файла: {total_file:,.2f} ₽\n"
                f"Общая сумма БД: {total_db:,.2f} ₽"
            ),
            parse_mode="HTML",
            reply_markup=get_delete_keyboard()
        )

        await processing_msg.delete()
        await state.clear()

    except Exception as e:
        logger.exception("Compare excel failed")
        await processing_msg.edit_text(f"Ошибка: {e}")
        await state.clear()


@router.message(Command("compare"), IsAdminFilter())
async def cmd_compare(message: Message, state: FSMContext):
    await delete_message(message)
    if message.from_user.id not in SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    date_match = re.search(r'/compare\s+(\d{2}\.\d{2}\.\d{4})', message.text)

    if date_match:
        target_date_str = date_match.group(1)
        try:
            target_date = datetime.strptime(target_date_str, "%d.%m.%Y")
        except ValueError:
            await temp_msg(message, "❌ Неверный формат даты. Используйте: ДД.ММ.ГГГГ\nПример: /compare 12.01.2026")
            return
    else:
        target_date = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)

    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1)

    await state.set_state(CompareStates.waiting_for_file)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_all")

    bot_message = await message.answer(
        f"<b>Чтобы сравнить данные в БД и файле</b>\n"
        f"Пришлите txt файл\n\n"
        f"Дата для сравнения: {target_date.strftime('%d.%m.%Y')}\n",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(
        start_date=start_date,
        end_date=end_date,
        target_date=target_date,
        initial_msg_id=bot_message.message_id,
    )

@router.message(CompareStates.waiting_for_file)
async def receive_file(message: Message, state: FSMContext):

    if not message.document.file_name.endswith('.txt'):
        await temp_msg(message, "❌ Требуется файл .txt")
        await state.clear()
        return

    data = await state.get_data()
    start_date = data["start_date"]
    end_date = data["end_date"]
    target_date = data["target_date"]
    initial_msg_id = data["initial_msg_id"]
    try:
        await message.bot.delete_message(message.chat.id, initial_msg_id)
    except:
        pass
    processing_msg = await message.answer(
        f"Обрабатываю файл...\n"
    )

    try:
        file = await message.bot.get_file(message.document.file_id)
        file_content = BytesIO()
        await message.bot.download_file(file.file_path, file_content)

        file_content.seek(0)
        lines = file_content.read().decode('utf-8').strip().split('\n')

        file_operations = []
        file_dates_set = set()

        for line in lines:
            if not line.strip():
                continue

            parts = line.split(';')
            if len(parts) < 5:
                continue

            try:
                contractor = parts[0].strip()
                transaction_id = parts[1].strip()
                date_time_str = parts[2].strip()
                operation_type = parts[3].strip()
                amount_str = parts[4].strip()

                file_date = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
                file_dates_set.add(file_date.date())

                amount = float(amount_str.replace(',', '.'))

                file_operations.append({
                    'contractor': contractor,
                    'transaction_id': transaction_id,
                    'datetime': file_date,
                    'operation_type': operation_type,
                    'amount': amount
                })
            except (ValueError, IndexError):
                continue

        if not file_operations:
            await processing_msg.edit_text("❌ В файле не найдено корректных операций")
            await state.clear()
            await delete_message(processing_msg)
            return

        target_date_only = target_date.date()
        if len(file_dates_set) == 1 and target_date_only not in file_dates_set:
            file_date_str = list(file_dates_set)[0].strftime('%d.%m.%Y')
            await processing_msg.edit_text(
                f"❌ Файл содержит операции за {file_date_str}, "
                f"а запрошена дата {target_date.strftime('%d.%m.%Y')}\n\n"
                f"Файл не за тот день!"
            )
            await state.clear()
            await delete_message(processing_msg)
            return

        db_operations_raw = await OperationRepo.get_all_checks_by_date(
            start_date,
            end_date
        )

        from collections import Counter
        file_amounts = Counter([op['amount'] for op in file_operations])
        db_amounts = Counter([float(op['amount']) for op in db_operations_raw])

        only_in_file = []
        only_in_db = []

        for amount, count in file_amounts.items():
            db_count = db_amounts.get(amount, 0)
            if count > db_count:
                diff = count - db_count
                matching_ops = [op for op in file_operations if op['amount'] == amount]
                only_in_file.extend(matching_ops[:diff])

        for amount, count in db_amounts.items():
            file_count = file_amounts.get(amount, 0)
            if count > file_count:
                diff = count - file_count
                matching_ops = [op for op in db_operations_raw if float(op['amount']) == amount]
                only_in_db.extend(matching_ops[:diff])

        if not only_in_file and not only_in_db:
            total_file = sum(op['amount'] for op in file_operations)
            total_db = sum(float(op['amount']) for op in db_operations_raw)

            await processing_msg.edit_text(
                f"<b>Все операции совпали!</b>\n\n"
                f"Статистика:\n"
                f"• В файле: {len(file_operations)} операций\n"
                f"• В базе: {len(db_operations_raw)} операций\n"
                f"• Общая сумма (файл): {total_file:,.2f} ₽\n"
                f"• Общая сумма (БД): {total_db:,.2f} ₽\n"
                f"• Дата: {target_date.strftime('%d.%m.%Y')}",
                parse_mode="HTML",
                reply_markup=get_delete_keyboard()
            )
            await state.clear()
            return

        await processing_msg.edit_text("📊 Найдены расхождения. Генерирую отчет...")


        buffer = await export_comparison_report(
            only_in_file=only_in_file,
            only_in_db=only_in_db,
        )

        filename = f"compare_{target_date.strftime('%Y%m%d')}.xlsx"

        total_coincided = len(file_operations) - len(db_operations_raw)

        await message.answer_document(
            document=BufferedInputFile(
                buffer.read(),
                filename=filename
            ),
            caption=(
                f"<b>Отчет о расхождениях</b>\n\n"
                f"🔴 Красным: есть в файле, нет в БД ({len(only_in_file)} шт.)\n"
                f"🟡 Желтым: есть в БД, нет в файле ({len(only_in_db)} шт.)\n\n"
                f"Дата: {target_date.strftime('%d.%m.%Y')}\n"
                f"Всего в файле: {len(file_operations)} операций\n"
                f"Всего в БД: {len(db_operations_raw)} операций\n"
                f"Совпало операций: {total_coincided}"
            ),
            parse_mode="HTML",
            reply_markup=get_delete_keyboard()
        )

        await processing_msg.delete()
        await state.clear()

    except Exception as e:
        await processing_msg.edit_text(f"❌ Ошибка при обработке: {str(e)}")


@router.message(Command("r"), IsAdminFilter())
async def cmd_daily_report(message: Message):
    await delete_message(message)

    if message.from_user.id not in SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return

    await generate_daily_report(message.bot, message.chat.id)

