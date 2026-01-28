import asyncpg
import logging
from datetime import date, timedelta
from typing import Optional, Dict, List
from database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class RateRepo(BaseRepository):

    @classmethod
    async def set_rate(cls, exchange_date: date, rate: float) -> None:
        """Установить или обновить курс для даты"""
        query = """
                INSERT INTO rate (exchange_date, rate)
                VALUES ($1, $2)
                ON CONFLICT (exchange_date)
                    DO UPDATE SET rate = EXCLUDED.rate \
                """
        await cls._execute(query, exchange_date, rate)
        logger.info(f"Rate set for {exchange_date}: {rate}")

    @classmethod
    async def get_rate_by_date(cls, exchange_date: date) -> Optional[float]:
        """Получить курс для конкретной даты"""
        query = "SELECT rate FROM rate WHERE exchange_date = $1"
        row = await cls._fetchrow(query, exchange_date)
        return float(row['rate']) if row else None

    @classmethod
    async def get_rate_for_period(cls, start_date: date, end_date: date) -> Dict[date, float]:
        """Получить все курсы за период"""
        query = """
                SELECT exchange_date, rate
                FROM rate
                WHERE exchange_date BETWEEN $1 AND $2
                ORDER BY exchange_date \
                """
        rows = await cls._fetch(query, start_date, end_date)
        return {row['exchange_date']: float(row['rate']) for row in rows}

    @classmethod
    async def get_all_rates(cls, limit: int = 100) -> List[Dict]:
        """Получить все курсы (для просмотра истории)"""
        query = """
                SELECT exchange_date, rate, created_at
                FROM rate
                ORDER BY exchange_date DESC
                LIMIT $1 \
                """
        rows = await cls._fetch(query, limit)
        return [dict(row) for row in rows]

    @classmethod
    async def get_latest_rate(cls) -> Optional[Dict]:
        """Получить последний записанный курс"""
        query = """
                SELECT exchange_date, rate, created_at
                FROM rate
                ORDER BY exchange_date DESC
                LIMIT 1 \
                """
        row = await cls._fetchrow(query)
        return dict(row) if row else None

    @classmethod
    async def delete_rate(cls, exchange_date: date) -> bool:
        """Удалить курс для даты"""
        query = "DELETE FROM rate WHERE exchange_date = $1"
        result = await cls._execute(query, exchange_date)
        return result == "DELETE 1"

    @classmethod
    async def fill_missing_dates(cls, start_date: date, end_date: date, default_rate: float) -> int:
        """Заполнить пропущенные даты одним курсом"""
        count = 0
        current = start_date

        while current <= end_date:
            existing = await cls._fetchval(
                "SELECT 1 FROM rate WHERE exchange_date = $1",
                current
            )

            if not existing:
                await cls._execute(
                    "INSERT INTO rate (exchange_date, rate) VALUES ($1, $2)",
                    current,
                    default_rate
                )
                count += 1

            current += timedelta(days=1)

        logger.info(f"Filled {count} missing dates with rate {default_rate}")
        return count

    @classmethod
    async def set_rate_for_period(cls, start_date: date, end_date: date, rate: float) -> int:
        """Установить курс для всех дат в периоде"""
        count = 0
        current = start_date

        async with cls._transaction() as conn:
            while current <= end_date:
                await conn.execute(
                    """
                    INSERT INTO rate (exchange_date, rate)
                    VALUES ($1, $2)
                    ON CONFLICT (exchange_date)
                        DO UPDATE SET rate = EXCLUDED.rate
                    """,
                    current,
                    rate
                )
                count += 1
                current += timedelta(days=1)

        logger.info(f"Set rate {rate} for period {start_date} - {end_date} ({count} days)")
        return count

    @classmethod
    async def rate_exists(cls, exchange_date: date) -> bool:
        """Проверить, существует ли курс для даты"""
        query = "SELECT EXISTS(SELECT 1 FROM rate WHERE exchange_date = $1)"
        return await cls._fetchval(query, exchange_date)

    @classmethod
    async def get_rates_count(cls) -> int:
        """Получить общее количество записей курсов"""
        query = "SELECT COUNT(*) FROM rate"
        return await cls._fetchval(query)

    @classmethod
    async def get_date_range(cls) -> Optional[Dict]:
        """Получить диапазон дат с курсами (минимальная и максимальная)"""
        query = """
                SELECT MIN(exchange_date) as min_date, \
                       MAX(exchange_date) as max_date, \
                       COUNT(*)           as total_records
                FROM rate \
                """
        row = await cls._fetchrow(query)
        return dict(row) if row else None

