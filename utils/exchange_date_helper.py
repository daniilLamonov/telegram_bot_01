from datetime import datetime, timedelta, date
from config import moscow_tz

def get_exchange_date_for_today() -> tuple[date, date]:
    now = datetime.now(moscow_tz).date()
    weekday = now.weekday()

    if weekday == 0:
        friday = now - timedelta(days=3)
        sunday = now - timedelta(days=1)
        return friday, sunday
    elif weekday == 1:
        monday = now - timedelta(days=1)
        return monday, monday
    else:
        prev_day = now - timedelta(days=1)
        return prev_day, prev_day


def get_date_range_text(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return start_date.strftime("%d.%m.%Y")
    else:
        return f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"


def get_weekday_name_ru(weekday: int) -> str:
    days = {
        0: "понедельник",
        1: "вторник",
        2: "среда",
        3: "четверг",
        4: "пятница",
        5: "суббота",
        6: "воскресенье"
    }
    return days.get(weekday, "неизвестный день")