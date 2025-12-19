from datetime import datetime
from typing import Optional, Tuple


def parse_date_period(
    cmd_text: str, command: str
) -> Tuple[Optional[datetime], Optional[datetime], Optional[str]]:
    args = cmd_text.replace(command, "").strip().split()
    if len(args) == 0 or args[0] == "@usssdt0_bot":
        return None, None, None  # без периода

    if len(args) == 1:
        start_date = datetime.strptime(args[0], "%d.%m.%Y")
        end_date = start_date.replace(hour=23, minute=59, second=59)
        print(start_date, end_date)
        return start_date, end_date, None

    try:
        start_date = datetime.strptime(args[0], "%d.%m.%Y")
        end_date = datetime.strptime(args[1], "%d.%m.%Y")
        end_date = end_date.replace(hour=23, minute=59, second=59)
        if start_date > end_date:
            return None, None, "❌ Дата начала не может быть позже даты окончания"
        return start_date, end_date, None
    except ValueError:
        return (
            None,
            None,
            "❌ Неверный формат дат. Используй DD.MM.YYYY (например: 11.11.2025 14.11.2025)",
        )
