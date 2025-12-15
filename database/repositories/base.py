import asyncpg
from typing import Optional, List, Any
from database.connection import get_pool


class BaseRepository:

    @classmethod
    async def _fetchrow(cls, query: str, *args) -> Optional[asyncpg.Record]:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @classmethod
    async def _fetch(cls, query: str, *args) -> List[asyncpg.Record]:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @classmethod
    async def _execute(cls, query: str, *args) -> str:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    @classmethod
    async def _fetchval(cls, query: str, *args) -> Any:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)
