import asyncpg
import logging
from typing import Optional, List, Any
from contextlib import asynccontextmanager
from database.connection import get_pool

logger = logging.getLogger(__name__)


class BaseRepository:

    @classmethod
    async def _fetchrow(cls, query: str, *args) -> Optional[asyncpg.Record]:
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        except asyncpg.PostgresError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    @classmethod
    async def _fetch(cls, query: str, *args) -> List[asyncpg.Record]:
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                return await conn.fetch(query, *args)
        except asyncpg.PostgresError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    @classmethod
    async def _execute(cls, query: str, *args) -> str:
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                return await conn.execute(query, *args)
        except asyncpg.PostgresError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    @classmethod
    async def _fetchval(cls, query: str, *args) -> Any:
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                return await conn.fetchval(query, *args)
        except asyncpg.PostgresError as e:
            logger.error(f"Database error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    @classmethod
    @asynccontextmanager
    async def _transaction(cls):
        """Контекстный менеджер для транзакций"""
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn
