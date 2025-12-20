import uuid
from typing import Optional, Any, Coroutine

from .base import BaseRepository


class BalanceRepo(BaseRepository):

    @classmethod
    async def create(cls, name: str,) -> dict:
        row = await cls._fetchrow("""
                                  INSERT INTO balances (name)
                                  VALUES ($1)
                                  RETURNING *
                                  """, name)
        return dict(row)

    @classmethod
    async def get_by_id(cls, balance_id: uuid.UUID) -> tuple[float, float]:
        row = await cls._fetchrow(
            """
            SELECT balance_rub, balance_usdt
            FROM balances
            WHERE id = $1
            """,
            balance_id,
        )
        return float(row["balance_rub"]), float(row["balance_usdt"])


    @classmethod
    async def get_by_name(cls, name: str) -> Optional[dict]:
        row = await cls._fetchrow("""
        SELECT id, name, balance_rub, balance_usdt, commission_percent
        FROM balances
            WHERE name = $1
        """, name)
        return dict(row) if row else None

    @classmethod
    async def get_by_chat(cls, chat_id: int) -> Optional[dict]:
        row = await cls._fetchrow(
            """
            SELECT b.id,
                   b.name,
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
    async def update(
        cls,
        balance_id: uuid.UUID,
        amount_rub: float = 0.0,
        amount_usdt: float = 0.0,
    ) -> dict:
        row = await cls._fetchrow(
            """
            UPDATE balances
            SET balance_rub  = $2,
                balance_usdt = $3,
                updated_at   = NOW()
            WHERE id = $1
            RETURNING balance_rub, balance_usdt
            """,
            balance_id,
            amount_rub,
            amount_usdt,
        )
        return dict(row)

    @classmethod
    async def get_commission(cls, balance_id: int) -> float:
        result = await cls._fetchval("""
            SELECT commission_percent
            FROM balances
            WHERE id = $1
            """, balance_id
        )
        return float(result) if result else 0.0


    @classmethod
    async def set_commission(cls, balance_id: uuid.UUID, percent: float):
        await cls._execute(
            """
            UPDATE balances
            SET commission_percent = $1,
                updated_at         = NOW()
            WHERE id = $2
            """,
            percent,
            balance_id,
        )

