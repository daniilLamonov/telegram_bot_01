import re
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramNetworkError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.markdown import html_decoration as hd

from config import logger
from database.repositories import ChatRepo, OperationRepo, BalanceRepo
from filters.admin import IsAdminFilter
from states import ReconciliationStates
from utils.helpers import delete_message, temp_msg
from utils.keyboards import get_delete_keyboard

router = Router(name="reconciliation")


@router.message(Command("history", "h"), IsAdminFilter())
async def cmd_h(message: Message):
    await delete_message(message)
    chat_id = message.chat.id

    balance_id = await ChatRepo.get_balance_id(chat_id)

    history = await OperationRepo.get_history(balance_id)

    if not history:
        await temp_msg(message, "📜 История операций пуста")
        return

    contractor = await BalanceRepo.get_contractor_name(balance_id)
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


@router.message(Command("sv"))
async def cmd_reconciliation(message: Message, state: FSMContext):
    await delete_message(message)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="sv_today"),
        InlineKeyboardButton(text="📆 Вчера", callback_data="sv_yesterday"),
    )
    builder.row(InlineKeyboardButton(text="📝 Ввести дату", callback_data="sv_custom"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="sv_cancel"))

    instruction_text = (
        "📊 <b>Сверка чеков</b>\n\n"
        "Выберите период для сверки:\n\n"
        "• <b>Сегодня</b> - все чеки за сегодня\n"
        "• <b>Вчера</b> - все чеки за вчерашний день\n"
        "• <b>Ввести дату</b> - конкретная дата или период\n\n"
        "Формат: <code>ДД.ММ.ГГГГ</code> или <code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
        "Пример: <code>12.01.2026 - 18.01.2026</code>"
    )

    bot_msg = await message.answer(
        instruction_text, parse_mode="HTML", reply_markup=builder.as_markup()
    )

    await state.update_data(sv_msg_id=bot_msg.message_id)


@router.callback_query(F.data == "sv_today")
async def sv_today(callback: CallbackQuery, state: FSMContext):
    await callback.answer("📅 Загрузка чеков за сегодня...")
    data = await state.get_data()
    sv_msg_id = data.get("sv_msg_id")

    balance_id = await ChatRepo.get_balance_id(callback.message.chat.id)

    try:
        if sv_msg_id:
            await callback.bot.delete_message(callback.message.chat.id, sv_msg_id)
    except Exception:
        pass

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    await show_checks_for_period(
        callback.message, balance_id, today, tomorrow, "Сегодня", state
    )


@router.callback_query(F.data == "sv_yesterday")
async def sv_yesterday(callback: CallbackQuery, state: FSMContext):
    """Сверка за вчера"""
    await callback.answer("📆 Загрузка чеков за вчера...")
    data = await state.get_data()
    sv_msg_id = data.get("sv_msg_id")

    balance_id = await ChatRepo.get_balance_id(callback.message.chat.id)

    try:
        if sv_msg_id:
            await callback.bot.delete_message(callback.message.chat.id, sv_msg_id)
    except Exception:
        pass

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    await show_checks_for_period(
        callback.message, balance_id, yesterday, today, "Вчера", state
    )


@router.callback_query(F.data == "sv_custom")
async def sv_custom(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    sv_msg_id = data.get("sv_msg_id")

    try:
        if sv_msg_id:
            await callback.bot.delete_message(callback.message.chat.id, sv_msg_id)
    except Exception:
        pass

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="sv_cancel")

    bot_msg = await callback.message.answer(
        "📝 <b>Введите дату или период сверки</b>\n\n"
        "Формат: <code>ДД.ММ.ГГГГ</code>\n"
        "Период: <code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
        "Пример: <code>12.01.2026 - 18.01.2026</code>\n\n"
        "Или <code>сегодня</code> / <code>вчера</code>",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

    await state.set_state(ReconciliationStates.waiting_for_date)
    await state.update_data(sv_msg_id=bot_msg.message_id)


@router.message(ReconciliationStates.waiting_for_date, F.text)
async def process_custom_date(message: Message, state: FSMContext):
    await delete_message(message)

    data = await state.get_data()
    sv_msg_id = data.get("sv_msg_id")

    balance_id = await ChatRepo.get_balance_id(message.chat.id)

    try:
        if sv_msg_id:
            await message.bot.delete_message(message.chat.id, sv_msg_id)
    except Exception:
        pass

    text = message.text.strip().lower()

    if text in ["сегодня", "today"]:
        target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        period_name = "Сегодня"
    elif text in ["вчера", "yesterday"]:
        target_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        period_name = "Вчера"
    else:
        parts = [p.strip() for p in re.split(r"\s*(?:-|–|—)\s*", text)]
        dates = []
        for part in parts:
            match = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", part)
            if not match or len(parts) > 2:
                dates = None
                break
            day, month, year = map(int, match.groups())
            try:
                dates.append(datetime(year, month, day))
            except ValueError:
                await temp_msg(
                    message,
                    "❌ <b>Некорректная дата!</b>\n\n" "Проверьте правильность даты.",
                    10,
                    parse_mode="HTML",
                )
                return

        if not dates:
            await temp_msg(
                message,
                "❌ <b>Неверный формат даты!</b>\n\n"
                "Используйте: <code>ДД.ММ.ГГГГ</code> или период "
                "<code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
                "Пример: <code>12.01.2026</code>",
                10,
                parse_mode="HTML",
            )
            return

        target_date = dates[0]
        period_name = target_date.strftime("%d.%m.%Y")
        if len(dates) == 2:
            if dates[1] < dates[0]:
                dates.reverse()
            target_date, last_date = dates
            period_name = (
                f"{target_date.strftime('%d.%m.%Y')} - {last_date.strftime('%d.%m.%Y')}"
            )
            await show_checks_for_period(
                message,
                balance_id,
                target_date,
                last_date + timedelta(days=1),
                period_name,
                state,
            )
            return

    next_date = target_date + timedelta(days=1)
    await show_checks_for_period(
        message, balance_id, target_date, next_date, period_name, state
    )


async def show_checks_for_period(
    message: Message,
    balance_id: int,
    start_date,
    end_date,
    period_name: str,
    state: FSMContext,
):
    checks = await OperationRepo.get_checks_by_date(balance_id, start_date, end_date)
    contractor_name = await BalanceRepo.get_contractor_name(balance_id)

    if not checks:
        await state.clear()
        await message.answer(
            f"📭 <b>Чеки не найдены</b>\n\n"
            f"За период: <b>{period_name}</b>\n"
            f"КА: {hd.quote(contractor_name)}",
            parse_mode="HTML",
            reply_markup=get_delete_keyboard(),
        )
        return

    total_amount = sum(check["amount"] for check in checks)
    time_fmt = "%d.%m %H:%M" if (end_date - start_date).days > 1 else "%H:%M"

    checks_list = []
    for idx, check in enumerate(checks, 1):
        desc = check["description"]
        payer_match = re.search(r"Плательщик: ([^.]+)", desc)
        payer = payer_match.group(1) if payer_match else "Не указано"

        time_str = check["timestamp"].strftime(time_fmt)

        checks_list.append(
            f"{idx}. <code>{check['operation_id'][:8]}</code> | "
            f"{time_str} | {check['amount']:.2f} ₽\n"
            f"   👤 {hd.quote(payer)}"
        )

    checks_text = "\n\n".join(checks_list)

    result_text = (
        f"📊 <b>Сверка чеков</b>\n\n"
        f"📅 Период: <b>{period_name}</b>\n"
        f"🏢 КА: {hd.quote(contractor_name)}\n\n"
        f"📋 <b>Найдено чеков: {len(checks)}</b>\n"
        f"💰 <b>Общая сумма: {total_amount:.2f} ₽</b>\n\n"
        f"{checks_text}\n\n"
        f"<i>Для просмотра чека:</i> <code>/hcheck ID</code>"
    )

    if len(result_text) > 4096:
        header = (
            f"📊 <b>Сверка чеков</b>\n\n"
            f"📅 Период: <b>{period_name}</b>\n"
            f"🏢 КА: {hd.quote(contractor_name)}\n\n"
            f"📋 <b>Найдено чеков: {len(checks)}</b>\n"
            f"💰 <b>Общая сумма: {total_amount:.2f} ₽</b>"
        )
        await message.answer(
            header, parse_mode="HTML", reply_markup=get_delete_keyboard()
        )

        chunk_size = 10
        for i in range(0, len(checks), chunk_size):
            chunk = checks[i : i + chunk_size]
            chunk_list = []
            for idx, check in enumerate(chunk, i + 1):
                desc = check["description"]
                payer_match = re.search(r"Плательщик: ([^.]+)", desc)
                payer = payer_match.group(1) if payer_match else "Не указано"
                time_str = check["timestamp"].strftime(time_fmt)

                chunk_list.append(
                    f"{idx}. <code>{check['operation_id'][:8]}</code> | "
                    f"{time_str} | {check['amount']:.2f} ₽\n"
                    f"   👤 {hd.quote(payer)}"
                )

            await message.answer(
                "\n\n".join(chunk_list),
                parse_mode="HTML",
                reply_markup=get_delete_keyboard(),
            )
    else:
        await message.answer(
            result_text, parse_mode="HTML", reply_markup=get_delete_keyboard()
        )

    await state.clear()


@router.callback_query(F.data == "sv_cancel")
async def sv_cancel(callback: CallbackQuery, state: FSMContext):

    try:
        await callback.answer("❌ Отменено")
    except TelegramBadRequest as e:
        if "query is too old" in str(e).lower():
            logger.warning(f"Callback query {callback.id} expired")
        else:
            logger.error(f"Bad request on callback answer: {e}")
    except TelegramNetworkError as e:
        logger.error(f"Network error answering callback {callback.id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error answering callback: {e}", exc_info=True)
    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
