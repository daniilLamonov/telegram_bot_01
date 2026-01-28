from datetime import datetime, timedelta, date
from config import moscow_tz

def get_exchange_date_for_today() -> tuple[date, date]:
    """
    Возвращает период дат, за который должен совершаться обмен сегодня.

    Логика:
    - Понедельник (weekday=0): обмениваем за пятницу-воскресенье (3 дня)
    - Вторник (weekday=1): обмениваем за понедельник (1 день)
    - Среда-воскресенье (weekday=2-6): обмениваем за предыдущий день (1 день)

    Возвращает кортеж (start_date, end_date)
    """
    now = datetime.now(moscow_tz).date()
    weekday = now.weekday()

    if weekday == 0:  # Понедельник
        friday = now - timedelta(days=3)
        sunday = now - timedelta(days=1)
        return friday, sunday
    elif weekday == 1:  # Вторник
        monday = now - timedelta(days=1)
        return monday, monday
    else:  # Среда-воскресенье
        prev_day = now - timedelta(days=1)
        return prev_day, prev_day


def get_date_range_text(start_date: date, end_date: date) -> str:
    """Возвращает текстовое представление периода"""
    if start_date == end_date:
        return start_date.strftime("%d.%m.%Y")
    else:
        return f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"


def get_weekday_name_ru(weekday: int) -> str:
    """Возвращает название дня недели на русском"""
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


def explain_exchange_logic() -> str:
    """Возвращает объяснение логики обмена для текущего дня"""
    now = datetime.now(moscow_tz).date()
    weekday = now.weekday()
    today_name = get_weekday_name_ru(weekday)

    start, end = get_exchange_date_for_today()
    period_text = get_date_range_text(start, end)

    if weekday == 0:
        explanation = f"Сегодня {today_name}, обмениваются чеки за выходные: {period_text}"
    elif weekday == 1:
        explanation = f"Сегодня {today_name}, обмениваются чеки за понедельник: {period_text}"
    else:
        explanation = f"Сегодня {today_name}, обмениваются чеки за вчера: {period_text}"

    return explanation
