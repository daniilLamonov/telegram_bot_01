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
        command_timeout=60
    )

    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id            BIGINT PRIMARY KEY,
                contractor_name    TEXT NOT NULL,
                commission_percent NUMERIC(5, 2)  DEFAULT 0,
                balance_rub        NUMERIC(15, 2) DEFAULT 0,
                balance_usdt       NUMERIC(15, 2) DEFAULT 0,
                chat_title         TEXT,
                chat_type          TEXT,
                is_active          BOOLEAN        DEFAULT true,
                initialized_by     BIGINT,
                created_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
                updated_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_chats_is_active
                ON chats (chat_id, is_active)
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS operations (
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

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id    BIGINT PRIMARY KEY,
                username   VARCHAR(255),
                first_name VARCHAR(255),
                last_name  VARCHAR(255),
                is_admin   BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')

        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_users_is_admin 
                ON users(is_admin)
        ''')

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()


def get_pool() -> asyncpg.Pool:
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return db_pool