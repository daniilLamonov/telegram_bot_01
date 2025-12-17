from typing import Optional, List
from .base import BaseRepository


class ChatRepo(BaseRepository):

    @classmethod
    async def get_chat(cls, chat_id: int) -> Optional[dict]:
        row = await cls._fetchrow("SELECT * FROM chats WHERE chat_id = $1", chat_id)
        return dict(row) if row else None

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
        contractor_name: str,
        initialized_by: int,
    ) -> bool:
        try:
            await cls._execute(
                """
                                INSERT INTO chats (chat_id, chat_title, chat_type, contractor_name, initialized_by,
                                                   is_active)
                                VALUES ($1, $2, $3, $4, $5, true)
                                ON CONFLICT (chat_id)
                                    DO UPDATE SET contractor_name = EXCLUDED.contractor_name,
                                                  chat_title      = EXCLUDED.chat_title,
                                                  is_active       = true,
                                                  updated_at      = NOW()
                                """,
                chat_id,
                chat_title,
                chat_type,
                contractor_name,
                initialized_by,
            )
            return True
        except Exception as e:
            return False

    @classmethod
    async def get_contractor_name(cls, chat_id: int) -> str:
        result = await cls._fetchval(
            "SELECT contractor_name FROM chats WHERE chat_id = $1", chat_id
        )
        return result if result else "Не установлено"

    @classmethod
    async def save_contractor_name(cls, chat_id: int, contractor_name: str):
        await cls._execute(
            """
                            INSERT INTO chats (chat_id, contractor_name)
                            VALUES ($1, $2)
                            ON CONFLICT (chat_id) DO UPDATE SET contractor_name = $2
                            """,
            chat_id,
            contractor_name,
        )

    @classmethod
    async def get_commission(cls, chat_id: int) -> float:
        result = await cls._fetchval(
            "SELECT commission_percent FROM chats WHERE chat_id = $1", chat_id
        )
        return float(result) if result else 0.0

    @classmethod
    async def set_commission(cls, chat_id: int, percent: float) -> bool:
        exists = await cls._fetchval(
            "SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1)", chat_id
        )
        if exists:
            await cls._execute(
                "UPDATE chats SET commission_percent = $1 WHERE chat_id = $2",
                percent,
                chat_id,
            )
            return True
        return False

    @classmethod
    async def get_balance(cls, chat_id: int) -> tuple[float, float]:
        result = await cls._fetchrow(
            "SELECT balance_rub, balance_usdt FROM chats WHERE chat_id = $1", chat_id
        )
        if not result:
            return (0.0, 0.0)
        return (float(result["balance_rub"]), float(result["balance_usdt"]))

    @classmethod
    async def update_balance(
        cls, chat_id: int, balance_rub: float, balance_usdt: float
    ):
        await cls._execute(
            """
                            UPDATE chats
                            SET balance_rub  = $1,
                                balance_usdt = $2,
                                updated_at   = CURRENT_TIMESTAMP
                            WHERE chat_id = $3
                            """,
            balance_rub,
            balance_usdt,
            chat_id,
        )

    @classmethod
    async def add_to_balance(
        cls, chat_id: int, amount_rub: float, amount_usdt: float = 0.0
    ):
        await cls._execute(
            """
                            UPDATE chats
                            SET balance_rub  = balance_rub + $1,
                                balance_usdt = balance_usdt + $2,
                                updated_at   = CURRENT_TIMESTAMP
                            WHERE chat_id = $3
                            """,
            amount_rub,
            amount_usdt,
            chat_id,
        )

    @classmethod
    async def get_all_chats(cls) -> List[dict]:
        results = await cls._fetch(
            """
                                    SELECT chat_id,
                                           contractor_name,
                                           balance_rub,
                                           balance_usdt,
                                           commission_percent,
                                           created_at,
                                           updated_at
                                    FROM chats
                                    ORDER BY contractor_name
                                    """
        )
        return [dict(row) for row in results]

    @classmethod
    async def get_all_active_chats(cls) -> list:
        rows = await cls._fetch(
            """
                SELECT chat_id, contractor_name, is_active
                FROM chats
                WHERE is_active = TRUE
                ORDER BY contractor_name \
            """
        )
        return [dict(row) for row in rows]

