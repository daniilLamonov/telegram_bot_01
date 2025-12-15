import asyncpg
from typing import Optional, List, Any


class BaseRepository:
    """Базовый репозиторий с общими методами для работы с БД"""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def _fetchrow(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Получить одну строку"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def _fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Получить несколько строк"""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def _execute(self, query: str, *args) -> str:
        """Выполнить запрос без возврата данных"""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def _fetchval(self, query: str, *args) -> Any:
        """Получить одно значение"""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
