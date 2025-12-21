import asyncpg
from typing import Optional
from config import settings

db_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global db_pool

    db_pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60,
        server_settings={"timezone": "Europe/Moscow"},
    )


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()


def get_pool() -> asyncpg.Pool:
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return db_pool
