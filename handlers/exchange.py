import re
from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings, logger
from database.repositories import OperationRepo, BalanceRepo, ChatRepo, RateRepo
from filters.admin import IsAdminFilter
from states import MassExchange
from utils.dateparse import parse_date_period
from utils.helpers import delete_message, temp_msg, format_amount
from utils.keyboards import get_delete_keyboard

router = Router(name="exchange")

moscow_tz = pytz.timezone('Europe/Moscow')



@router.message(Command("ch"), IsAdminFilter())
async def cmd_ch(message: Message):
    await delete_message(message)
    match = re.search(r"/ch\s+(\d+(?:[.,]\d+)?)\s+([\d\s.,]+)", message.text)
    if not match:
        await temp_msg(
            message,
            "❌ <b>Неверный формат!</b>\n\n"
            "Формат: <b>/ch курс сумма</b>\n\n"
            "Примеры:\n"
            "• /ch 95 5 000 000\n"
            "• /ch 95,5 1 000 000\n"
            "• /ch 100 500 000",
            parse_mode="HTML",
        )
        return

    try:
        rate = float(match.group(1).replace(",", "."))

        amount_str = (
            match.group(2).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        )
        amount_rub = float(amount_str)

        if rate <= 0 or amount_rub <= 0:
            await temp_msg(message, "❌ Курс и сумма должны быть > 0")
            return

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        balance = await BalanceRepo.get_by_chat(chat_id)

        balance_id = balance["id"]

        balance_rub, balance_usdt = balance["balance_rub"], balance["balance_usdt"]

        if balance_rub < amount_rub:
            await temp_msg(
                message,
                f"❌ Недостаточно средств на балансе ₽\nБаланс чата: {balance_rub:.2f} ₽",
            )
            return
        
        amount_usdt = amount_rub / rate
        commission = float(balance["commission_percent"])
        amount_after_commission, commission_amount = await calculate_commission(
            balance_id, amount_usdt, user_id, username, commission
        )

        # Используем атомарное списание с проверкой баланса
        success = await BalanceRepo.subtract_atomic(balance_id, amount_rub, 0.0)
        if not success:
            await temp_msg(
                message,
                f"❌ Недостаточно средств на балансе ₽\nБаланс чата: {balance_rub:.2f} ₽",
            )
            return
        
        # Пополняем USDT баланс
        await BalanceRepo.add(balance_id, 0.0, amount_after_commission)

        await OperationRepo.log_operation(
            balance_id,
            user_id,
            username,
            "обмен_руб_на_usdt",
            amount_rub,
            "RUB",
            exchange_rate=rate,
            description=f"Получено: {amount_usdt:.2f} USDT",
        )

        await message.answer(
            (
                f"Обмен выполнен ✅\n\n"
                f"{amount_rub:.2f} ₽ списано \n"
                f"{rate} курс\n"
                f"{commission_amount:.2f}$ комиссия в чате ({commission}%)\n"
                f"{amount_after_commission:.2f}$ пополнен баланс"
            ).replace(".", ","),
            reply_markup=get_delete_keyboard(),
        )
    except (ValueError, IndexError):
        await temp_msg(message, "Ошибка: введите корректные значения")


@router.message(Command("chall"), IsAdminFilter())
async def cmd_chall(message: Message, state: FSMContext):
    if message.from_user.id not in settings.SUPER_ADMIN_ID:
        await temp_msg(message, "❌ У вас нет прав для этой команды")
        return
    await delete_message(message)

    text_parts = message.text.strip().split(maxsplit=1)

    if len(text_parts) == 1:
        # Команда без параметров - автоматический режим
        # Определяем только дату для установки курса (вчерашний день)
        today = datetime.now(moscow_tz).date()
        yesterday = today - timedelta(days=1)

        # Обмениваем ВСЕ чеки с начала времен до конца вчерашнего дня
        start_date = datetime(2020, 1, 1)  # Очень ранняя дата
        end_date = datetime.combine(yesterday, datetime.max.time()).replace(hour=23, minute=59, second=59)

        await state.set_state(MassExchange.waiting_rate)

        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data="cancel_all")

        bot_message = await message.answer(
            f"<b>📅 Автоматический обмен чеков</b>\n\n"
            f"Период обмена: <b>{yesterday.strftime('%d.%m.%Y')}</b>\n\n"
            f"<i>Будут обменены все чеки до {yesterday.strftime('%d.%m.%Y')} включительно.\n"
            f"Для других дат будут использованы курсы из таблицы.</i>\n\n"
            "💱 Укажите курс для <b>{}</b>:".format(yesterday.strftime('%d.%m.%Y')),
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )

        await state.update_data(
            start_date=start_date,
            end_date=end_date,
            target_date=yesterday,  # Дата, для которой устанавливается курс
            initial_msg_id=bot_message.message_id,
            auto_mode=True
        )
    else:
        # Ручное указание дат - старая логика
        start_date, end_date, err = parse_date_period(message.text, "/chall")
        now_date = datetime.now(moscow_tz).replace(tzinfo=None)

        if end_date is None:
            await temp_msg(message, "❌ Необходимо указать даты")
            return

        if end_date >= now_date:
            err = "❌ Нельзя обменивать чеки за сегодня"

        if err:
            await temp_msg(message, err)
            return

        await state.set_state(MassExchange.waiting_rate)

        builder = InlineKeyboardBuilder()
        builder.button(text="❌ Отмена", callback_data="cancel_all")

        bot_message = await message.answer(
            f"<b>📅 Ручной обмен чеков за период</b>\n\n"
            f"С <b>{start_date.strftime('%d.%m.%Y')}</b> по <b>{end_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"<i>Курс будет установлен для всех дат периода.</i>\n\n"
            "💱 Укажите курс обмена:",
            parse_mode="HTML",
            reply_markup=builder.as_markup(),
        )

        await state.update_data(
            start_date=start_date,
            end_date=end_date,
            target_date=None,  # В ручном режиме курс для всего периода
            initial_msg_id=bot_message.message_id,
            auto_mode=False
        )


@router.message(MassExchange.waiting_rate)
async def receive_rate(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip().replace(",", ".")
    try:
        rate = float(text)
    except (ValueError, TypeError):
        await temp_msg(
            message,
            "❌ Курс должен быть числом. Пример: <code>95.5</code>",
            parse_mode="HTML"
        )
        return
    if rate <= 0:
        await temp_msg(message, "❌ Курс должен быть больше нуля")
        return

    data = await state.get_data()
    start_date = data["start_date"]
    end_date = data["end_date"]
    target_date = data.get("target_date")  # Дата для установки курса
    is_auto_mode = data.get("auto_mode", False)

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    balances = await BalanceRepo.get_all()

    report_lines = [f"<b>💱 Массовый обмен</b>\n"]
    if is_auto_mode:
        report_lines.append(f"🤖 Режим: Автоматический")
        report_lines.append(f"📅 Курс установлен для: {target_date.strftime('%d.%m.%Y')}")
    else:
        report_lines.append(f"📅 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
    report_lines.append("")

    total_rub = 0
    total_usdt = 0
    total_commission = 0
    successful_chats = 0
    gen_chats = await ChatRepo.get_general_chats()

    # Если автоматический режим - сохраняем курс только для target_date
    # Если ручной - сохраняем для всего периода
    if is_auto_mode and target_date:
        await RateRepo.set_rate(target_date, rate)
    else:
        # Ручной режим - устанавливаем курс для всех дат периода
        current_date = start_date.date()
        end_date_only = end_date.date()

        while current_date <= end_date_only:
            await RateRepo.set_rate(current_date, rate)
            current_date += timedelta(days=1)

    # Получаем курсы за весь возможный период
    all_rates = await RateRepo.get_rate_for_period(
        start_date.date(),
        end_date.date()
    )

    for balance in balances:
        balance_id = balance["id"]
        contractor_name = balance["name"]
        chats = await ChatRepo.get_by_balance_id(balance_id)
        commission = float(balance["commission_percent"])

        # Получаем ВСЕ необмененные чеки за период
        operations = await OperationRepo.get_checks_by_date(balance_id, start_date, end_date)

        amount_rub = 0
        operations_by_rate = {}  # Группируем операции по курсу для статистики
        checks_without_rate = []  # Чеки, для которых нет курса

        for operation in operations:
            operation_id = operation["operation_id"]
            op_timestamp = operation["timestamp"]
            op_date = op_timestamp.date()

            # Обрабатываем только чеки без курса (еще не обменянные)
            if operation["exchange_rate"] is None:
                # Определяем курс для этого чека
                check_rate = all_rates.get(op_date)

                if check_rate is None:
                    # Если для даты чека нет курса в таблице
                    checks_without_rate.append({
                        'date': op_date,
                        'operation_id': operation_id,
                        'amount': float(operation["amount"])
                    })
                    continue  # Пропускаем этот чек - нет курса

                op_amount = float(operation["amount"])
                amount_rub += op_amount

                # Группируем по курсу для детализации
                if check_rate not in operations_by_rate:
                    operations_by_rate[check_rate] = {
                        'amount': 0,
                        'count': 0,
                        'dates': set()
                    }
                operations_by_rate[check_rate]['amount'] += op_amount
                operations_by_rate[check_rate]['count'] += 1
                operations_by_rate[check_rate]['dates'].add(op_date)

                # Обновляем курс в операции
                await OperationRepo.update_operation(
                    operation_id,
                    exchange_rate=check_rate
                )

        if amount_rub == 0:
            if checks_without_rate:
                dates_str = ", ".join(sorted(set([c['date'].strftime('%d.%m') for c in checks_without_rate])))
                report_lines.append(
                    f"\n⚠️ <code>{contractor_name}</code>: есть чеки без курса\n"
                    f"   Даты: {dates_str}"
                )
            else:
                report_lines.append(f"\n⚪️ <code>{contractor_name}</code>: нет чеков для обмена")
            continue

        # Рассчитываем общую сумму USDT с учетом разных курсов
        amount_usdt = 0
        for check_rate, rate_data in operations_by_rate.items():
            amount_usdt += rate_data['amount'] / check_rate

        amount_after_commission, commission_amount = await calculate_commission(
            balance_id, amount_usdt, user_id, username, commission
        )

        success = await BalanceRepo.subtract_atomic(balance_id, amount_rub, 0.0)
        if not success:
            report_lines.append(
                f"\n❌ <code>{contractor_name}</code>: недостаточно средств"
            )
            continue

        await BalanceRepo.add(balance_id, 0.0, amount_after_commission)

        # Формируем описание для операции обмена
        rate_details_str = ", ".join([
            f"{r}₽ ({d['count']}шт)"
            for r, d in sorted(operations_by_rate.items())
        ])

        await OperationRepo.log_operation(
            balance_id,
            user_id,
            username,
            "обмен_руб_на_usdt",
            amount_rub,
            "RUB",
            exchange_rate=rate if not is_auto_mode else list(operations_by_rate.keys())[0] if len(
                operations_by_rate) == 1 else rate,
            description=f"Курсы: {rate_details_str}. Получено: {amount_usdt:.2f} USDT",
        )

        f_amount_rub = format_amount(amount_rub)
        f_amount_usdt = format_amount(amount_usdt)

        # Детализация по курсам для отчета
        rate_details = []
        for check_rate in sorted(operations_by_rate.keys()):
            rate_data = operations_by_rate[check_rate]
            dates_str = ", ".join(sorted([d.strftime("%d.%m") for d in rate_data['dates']]))
            rate_details.append(
                f"  • Курс {check_rate}: {rate_data['count']} чек(ов) на {format_amount(rate_data['amount'])} ₽\n"
                f"    Даты: {dates_str}"
            )

        chat_report = (
            f"\n✅ <code>{contractor_name}</code>:\n"
            f"📋 Чеков обработано: {len([o for o in operations if o['exchange_rate'] is None]) - len(checks_without_rate)}\n"
            f"💸 Списано: {f_amount_rub} ₽\n"
            f"💵 Получено: {f_amount_usdt} USDT\n"
            f"💰 Комиссия: {commission_amount:.2f} USDT ({commission}%)\n"
            f"✨ К балансу: {amount_after_commission:.2f} USDT\n"
        )

        if len(operations_by_rate) > 1 or is_auto_mode:
            chat_report += f"\n📊 Детализация по курсам:\n" + "\n".join(rate_details)

        if checks_without_rate:
            dates_without_rate = sorted(set([c['date'].strftime('%d.%m') for c in checks_without_rate]))
            chat_report += f"\n\n⚠️ Не обменяно {len(checks_without_rate)} чек(ов) без курса:\n   {', '.join(dates_without_rate)}"

        report_lines.append(chat_report)

        # Отправка уведомлений в чаты
        for chat_id in chats:
            if chat_id in gen_chats:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=chat_report,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки в чат {chat_id}: {e}")

        total_rub += amount_rub
        total_usdt += amount_after_commission
        total_commission += commission_amount
        successful_chats += 1

    f_total_rub = format_amount(total_rub)
    f_total_usdt = format_amount(total_usdt)

    report_lines.append(
        f"\n\n📊 <b>Итоговая статистика:</b>\n"
        f"✅ Обработано балансов: {successful_chats}\n"
        f"💸 Всего списано: {f_total_rub} ₽\n"
        f"💵 Всего получено: {f_total_usdt} USDT\n"
        f"💰 Всего комиссия: {total_commission:.2f} USDT"
    )

    if is_auto_mode and target_date:
        report_lines.append(f"📈 Курс для {target_date.strftime('%d.%m.%Y')}: {rate}")
    else:
        report_lines.append(f"📈 Установленный курс: {rate}")

    report = "\n".join(report_lines).replace(".", ",")

    await message.answer(report, parse_mode="HTML", reply_markup=get_delete_keyboard())
    await state.clear()


async def calculate_commission(balance_id, amount_usdt, user_id, username, commission):
    commission_amount = amount_usdt * (commission / 100)
    amount_after_commission = amount_usdt - commission_amount

    await OperationRepo.log_operation(
        balance_id,
        user_id,
        username,
        "комиссия",
        commission_amount,
        "USDT",
        description=f"Комиссия на момент обмена: {commission}%"
    )
    return amount_after_commission, commission_amount


@router.callback_query(F.data == "cancel_all")
async def cancel_all_files(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    message_to_delete = data.get("initial_msg_id")

    if message_to_delete:
        try:
            await callback.bot.delete_message(callback.message.chat.id, message_to_delete)
        except Exception:
            pass

    await state.clear()