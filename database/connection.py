import asyncpg
from typing import Optional
from config import settings
db_pool: Optional[asyncpg.Pool] = None


async def init_db():
    global db_pool

    db_pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)

    async with db_pool.acquire() as conn:
        await conn.execute('''
                           CREATE TABLE IF NOT EXISTS chats
                           (
                               chat_id            BIGINT PRIMARY KEY,
                               contractor_name    TEXT,
                               commission_percent NUMERIC(5, 2)  DEFAULT 0,
                               balance_rub        NUMERIC(15, 2) DEFAULT 0,
                               balance_usdt       NUMERIC(15, 2) DEFAULT 0,
                               created_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                               updated_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
                           )
                           ''')

        await conn.execute('''
                           CREATE TABLE IF NOT EXISTS operations
                           (
                               id             SERIAL PRIMARY KEY,
                               operation_id   TEXT UNIQUE    NOT NULL,
                               chat_id        BIGINT         NOT NULL,
                               user_id        BIGINT         NOT NULL,
                               username       TEXT,
                               operation_type TEXT           NOT NULL,
                               amount         NUMERIC(15, 2) NOT NULL,
                               currency       TEXT           NOT NULL,
                               exchange_rate  NUMERIC(15, 4),
                               timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                               description    TEXT
                           )
                           ''')

        await conn.execute('''
                           CREATE INDEX IF NOT EXISTS idx_operations_chat
                               ON operations (chat_id)
                           ''')

        await conn.execute('''
                           CREATE INDEX IF NOT EXISTS idx_operations_timestamp
                               ON operations (timestamp DESC)
                           ''')


async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()

def get_pool() -> asyncpg.Pool:
    """Получить пул подключений"""
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return db_pool