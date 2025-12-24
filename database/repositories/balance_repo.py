import uuid
import logging
from typing import Optional, Any, Coroutine
from database.connection import get_pool

from .base import BaseRepository

logger = logging.getLogger(__name__)


class BalanceRepo(BaseRepository):
    @classmethod
    async def create(
        cls,
        name: str,
    ) -> dict:
        row = await cls._fetchrow(
            """
                                  INSERT INTO balances (name)
                                  VALUES ($1)
                                  RETURNING *
                                  """,
            name,
        )
        return dict(row)

    @classmethod
    async def get_by_id(cls, balance_id: uuid.UUID) -> dict[str, Any]:
        row = await cls._fetchrow(
            """
            SELECT *
            FROM balances
            WHERE id = $1
            """,
            balance_id,
        )
        return dict(row) if row else None

    @classmethod
    async def get_by_name(cls, name: str) -> Optional[dict]:
        row = await cls._fetchrow(
            """
        SELECT id, name, balance_rub, balance_usdt, commission_percent
        FROM balances
            WHERE name = $1
        """,
            name,
        )
        return dict(row) if row else None

    @classmethod
    async def get_by_chat(cls, chat_id: int) -> Optional[dict]:
        row = await cls._fetchrow(
            """
            SELECT b.*
            FROM chats c
                     JOIN balances b ON c.balance_id = b.id
            WHERE c.chat_id = $1
            """,
            chat_id,
        )
        return dict(row) if row else None

    @classmethod
    async def get_all(cls) -> list[dict]:
        results = await cls._fetch(
            """
                  SELECT *
                  FROM balances
                  ORDER BY name
                  """
        )
        return [dict(row) for row in results]

    @classmethod
    async def add(
        cls,
        balance_id: uuid.UUID,
        amount_rub: float = 0.0,
        amount_usdt: float = 0.0,
    ):
        await cls._execute(
            """
            UPDATE balances
            SET balance_rub  = balance_rub + $2,
                balance_usdt = balance_usdt + $3,
                updated_at   = NOW()
            WHERE id = $1
            """,
            balance_id,
            amount_rub,
            amount_usdt,
        )

    @classmethod
    async def subtract_atomic(
        cls,
        balance_id: uuid.UUID,
        amount_rub: float = 0.0,
        amount_usdt: float = 0.0,
    ) -> bool:
        """
        Атомарное списание с проверкой баланса в транзакции.
        Возвращает True если операция успешна, False если недостаточно средств.
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Проверяем текущий баланс с блокировкой строки
                balance = await conn.fetchrow(
                    """
                    SELECT balance_rub, balance_usdt
                    FROM balances
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    balance_id,
                )
                
                if not balance:
                    logger.warning(f"Баланс с id {balance_id} не найден")
                    return False
                
                new_rub = float(balance['balance_rub']) - amount_rub
                new_usdt = float(balance['balance_usdt']) - amount_usdt
                
                if new_rub < 0 or new_usdt < 0:
                    logger.warning(
                        f"Недостаточно средств на балансе {balance_id}. "
                        f"Требуется: RUB={amount_rub}, USDT={amount_usdt}. "
                        f"Доступно: RUB={balance['balance_rub']}, USDT={balance['balance_usdt']}"
                    )
                    return False
                
                # Выполняем списание
                await conn.execute(
                    """
                    UPDATE balances
                    SET balance_rub  = $2,
                        balance_usdt = $3,
                        updated_at   = NOW()
                    WHERE id = $1
                    """,
                    balance_id,
                    new_rub,
                    new_usdt,
                )
                
                return True

    @classmethod
    async def get_commission(cls, balance_id: int) -> float:
        result = await cls._fetchval(
            """
            SELECT commission_percent
            FROM balances
            WHERE id = $1
            """,
            balance_id,
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

    @classmethod
    async def get_contractor_name(cls, balance_id: int) -> str:
        result = await cls._fetchval("""
                SELECT name
                FROM balances
                WHERE id = $1
                """, balance_id
        )
        return result if result else "Не установлено"