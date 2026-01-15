import re
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from database.repositories import ChatRepo, OperationRepo, BalanceRepo
from filters.admin import IsAdminFilter
from states import CompareStates
from utils.excel import export_to_excel, export_comparison_report
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
    await delete_message(initial_msg_id)

    processing_msg = await message.answer(
        f"⏳ Обрабатываю файл...\n"
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
                f"✅ <b>Все операции совпали!</b>\n\n"
                f"📊 Статистика:\n"
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

    now = datetime.now(moscow_tz).replace(tzinfo=None)
    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

    all_balances = await BalanceRepo.get_all()

    report_lines = []
    total_checks = 0
    total_amount = 0.0

    for balance in all_balances:
        balance_id = balance["id"]
        contractor_name = balance["name"]

        if contractor_name == "__default__":
            continue

        checks = await OperationRepo.get_checks_by_date(balance_id, start_date, now)

        if not checks:
            continue

        count = len(checks)
        amount = sum(float(check['amount']) for check in checks)

        total_checks += count
        total_amount += amount

        if amount == int(amount):
            formatted_amount = f'{int(amount):,}'.replace(',', ' ')
        else:
            formatted_amount = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')

        if count % 10 == 1 and count % 100 != 11:
            check_word = "чек"
        elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
            check_word = "чека"
        else:
            check_word = "чеков"

        report_lines.append(f"{contractor_name} - {count} {check_word} {formatted_amount}₽")

    if not report_lines:
        await message.answer(
            f"📊 Отчёт за {now.strftime('%d.%m.%Y')}\n\n"
            "Сегодня ещё не было чеков",
            reply_markup=get_delete_keyboard()
        )
        return

    if total_amount == int(total_amount):
        formatted_total = f'{int(total_amount):,}'.replace(',', ' ')
    else:
        formatted_total = f'{total_amount:,.2f}'.replace(',', ' ').replace('.', ',')

    if total_checks % 10 == 1 and total_checks % 100 != 11:
        total_check_word = "чек"
    elif 2 <= total_checks % 10 <= 4 and (total_checks % 100 < 10 or total_checks % 100 >= 20):
        total_check_word = "чека"
    else:
        total_check_word = "чеков"

    report_lines.sort(key=lambda x: float(x.split()[-1].replace(' ', '').replace('₽', '').replace(',', '.')),
                      reverse=True)

    report_text = (
            f"📊 <b>Количество чеков + сумма {now.strftime('%d.%m.%Y')}:</b>\n\n"
            + "\n".join(report_lines) +
            f"\n\n<b>Общее количество чеков = {total_checks} {total_check_word}</b>\n"
            f"<b>Общая сумма = {formatted_total}₽</b>"
    )

    await message.answer(
        report_text,
        parse_mode="HTML",
        reply_markup=get_delete_keyboard()
    )

