from datetime import datetime
from aiogram import Bot
from aiogram.enums import ParseMode

from database.repositories import BalanceRepo, OperationRepo
from config import moscow_tz


async def generate_daily_report(bot: Bot, chat_id: int):
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
        await bot.send_message(
            chat_id=chat_id,
            text=f"📊 Отчёт за {now.strftime('%d.%m.%Y')}\n\nСегодня ещё не было чеков"
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

    await bot.send_message(
        chat_id=chat_id,
        text=report_text,
        parse_mode=ParseMode.HTML
    )
