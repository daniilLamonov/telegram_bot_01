from typing import Optional
from .base import BaseRepository
from config import logger


class ChatRepo(BaseRepository):
    @classmethod
    async def get_chat(cls, chat_id: int) -> Optional[dict]:
        row = await cls._fetchrow(
            """
            SELECT
                c.chat_id,
                c.chat_title,
                c.chat_type,
                c.is_active,
                c.initialized_by,
                c.created_at,
                c.updated_at,
                c.balance_id,
                b.name                AS balance_name,
                b.balance_rub,
                b.balance_usdt,
                b.commission_percent
            FROM chats c
            JOIN balances b ON c.balance_id = b.id
            WHERE c.chat_id = $1
            """,
            chat_id,
        )
        return dict(row) if row else None

    @classmethod
    async def get_balance_id(cls, chat_id: int):
        return await cls._fetchval(
            "SELECT balance_id FROM chats WHERE chat_id = $1",
            chat_id,
        )

    @classmethod
    async def is_chat_initialized(cls, chat_id: int) -> bool:
        result = await cls._fetchval(
            "SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1 AND is_active = true)",
            chat_id,
        )
        return result or False

    @classmethod
    async def initialize_chat(
        cls,
        chat_id: int,
        chat_title: str,
        chat_type: str,
        initialized_by: int,
        balance_id,
    ) -> bool:
        try:
            await cls._execute(
                """
                INSERT INTO chats (
                    chat_id,
                    chat_title,
                    chat_type,
                    initialized_by,
                    is_active,
                    balance_id
                )
                VALUES ($1, $2, $3, $4, TRUE, $5)
                ON CONFLICT (chat_id)
                DO UPDATE SET
                    chat_title      = EXCLUDED.chat_title,
                    chat_type       = EXCLUDED.chat_type,
                    balance_id      = EXCLUDED.balance_id,
                    is_active       = TRUE,
                    updated_at      = NOW()
                """,
                chat_id,
                chat_title,
                chat_type,
                initialized_by,
                balance_id,
            )
            return True
        except Exception:
            return False

    @classmethod
    async def get_all_active_chats(cls) -> list:
        rows = await cls._fetch(
            """
                SELECT chat_id, is_active
                FROM chats
                WHERE is_active = TRUE
            """
        )
        return [dict(row) for row in rows]


    @classmethod
    async def update_balance(cls, chat_id: int, balance_id: str) -> bool:
        try:
            await cls._execute(
                """
                UPDATE chats
                SET balance_id = $2,
                    updated_at = NOW()
                WHERE chat_id = $1
                """,
                chat_id,
                balance_id,
            )
            return True
        except Exception as e:
            logger(f"Ошибка обновления баланса чата: {e}")
            return False

    @classmethod
    async def get_by_balance_id(cls, balance_id: str) -> list[int]:
        try:
            rows = await cls._fetch(
                """
                SELECT chat_id
                FROM chats
                WHERE balance_id = $1
                """,
                balance_id,
            )
            return [row["chat_id"] for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return []

    @classmethod
    async def set_general_status(cls, chat_id: int, is_general: bool) -> bool:
        try:
            result = await cls._fetchval(
                """
                UPDATE chats
                SET is_general = $1
                WHERE chat_id = $2
                RETURNING chat_id
                """,
                is_general,
                chat_id,
            )
            return result is not None
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return False

    @classmethod
    async def get_general_chats(cls) -> list:
        try:
            rows = await cls._fetch(
                """
                SELECT chat_id
                FROM chats
                WHERE is_general = TRUE
                """
            )
            return [row["chat_id"] for row in rows] if rows else []
        except Exception as e:
            logger.error(f"Ошибка обновления баланса чата: {e}")
            return []
