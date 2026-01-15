import re
from datetime import datetime, timedelta
import pytz
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings, logger
from database.repositories import OperationRepo, BalanceRepo, ChatRepo
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

    start_date, end_date, err = parse_date_period(message.text, "/chall")
    now_date = datetime.now(moscow_tz).replace(tzinfo=None)

    if end_date is None:
        await temp_msg(message, "Необходимо указать даты")
        return

    if end_date >= now_date:
        err = "Нельзя обменивать чеки за сегодня"

    if err:
        await temp_msg(message, err)
        return

    await state.set_state(MassExchange.waiting_rate)

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_all")

    bot_message = await message.answer(
        f"<b>Если вы уверены, что хотите совершить обмен всех чеков за период</b>\n"
        f"<b>С {start_date} по {end_date}</b>\n"
        "Укажите курс просто числом:",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.update_data(
        start_date=start_date,
        end_date=end_date,
        initial_msg_id=bot_message.message_id,
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

    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    balances = await BalanceRepo.get_all()

    report_lines = [f"<b>Массовый обмен по курсу: {rate}</b>\n"]
    report_lines.append(f"Период: {start_date.strftime('%d.%m.%Y')}\n")

    total_rub = 0
    total_usdt = 0
    total_commission = 0
    successful_chats = 0
    gen_chats = await ChatRepo.get_general_chats()

    for balance in balances:
        balance_id = balance["id"]
        contractor_name = balance["name"]
        chats = await ChatRepo.get_by_balance_id(balance_id)
        commission = float(balance["commission_percent"])
        operations = await OperationRepo.get_checks_by_date(balance_id, start_date, end_date)
        amount_rub = 0
        for operation in operations:
            operation_id = operation["operation_id"]
            if operation["exchange_rate"] is None:
                amount_rub += float(operation["amount"])
                await OperationRepo.update_operation(
                    operation_id,
                    exchange_rate=rate)
            else:
                continue

        if amount_rub == 0:
            report_lines.append(f"\n⚪️ Чат <code>{contractor_name}</code>: нет чеков для обмена")

        else:
            amount_usdt = amount_rub / rate
            amount_after_commission, commission_amount = await calculate_commission(
                balance_id, amount_usdt, user_id, username, commission
            )
            success = await BalanceRepo.subtract_atomic(balance_id, amount_rub, 0.0)
            if not success:
                report_lines.append(
                    f"\n❌ Чат <code>{contractor_name}</code>: недостаточно средств для обмена"
                )
                continue
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
            f_amount_rub = format_amount(amount_rub)
            f_amount_usdt = format_amount(amount_usdt)
            chat_report = (
                f"\n✅ Баланс <code>{contractor_name}</code>:\n"
                f"Чеков за период: {len(operations)}\n"
                f"Списано: {f_amount_rub} ₽\n"
                f"Получено: {f_amount_usdt} USDT\n"
                f"Комиссия: {commission_amount:.2f} USDT ({commission}%)\n"
                f"К балансу: {amount_after_commission:.2f} USDT"
                f"Период списания: {start_date} - {end_date}"
            )
            report_lines.append(chat_report)
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
        f"\n\n📊 <b>Итого:</b>\n"
        f"✅ Обработано чатов: {successful_chats}\n"
        f"💸 Всего списано: {f_total_rub} ₽\n"
        f"💵 Всего получено: {f_total_usdt} USDT\n"
        f"💰 Всего комиссия: {total_commission:.2f} USDT"
    )
    report = "\n".join(report_lines).replace(".", ",")

    await message.answer(report, parse_mode="HTML", reply_markup=get_delete_keyboard())


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