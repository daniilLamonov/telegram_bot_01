import asyncpg
import logging
from datetime import date, timedelta
from typing import Optional, Dict, List
from database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class RateRepo(BaseRepository):

    @classmethod
    async def set_rate(cls, exchange_date: date, rate: float) -> None:
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
        query = "SELECT rate FROM rate WHERE exchange_date = $1"
        row = await cls._fetchrow(query, exchange_date)
        return float(row['rate']) if row else None

    @classmethod
    async def get_rate_for_period(cls, start_date: date, end_date: date) -> Dict[date, float]:
        query = """
                SELECT exchange_date, rate
                FROM rate
                WHERE exchange_date BETWEEN $1 AND $2
                ORDER BY exchange_date \
                """
        rows = await cls._fetch(query, start_date, end_date)
        return {row['exchange_date']: float(row['rate']) for row in rows}


