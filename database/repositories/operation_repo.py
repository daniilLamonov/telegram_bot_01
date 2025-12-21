import uuid
from typing import Optional, List
from datetime import datetime
from .base import BaseRepository


class OperationRepo(BaseRepository):
    @classmethod
    async def log_operation(
        cls,
        balance_id: int,
        user_id: int,
        username: str,
        op_type: str,
        amount: float,
        currency: str,
        exchange_rate: Optional[float] = None,
        description: str = "",
    ) -> str:
        operation_id = str(uuid.uuid4())[:8]
        await cls._execute(
            """
                           INSERT INTO operations
                           (operation_id, balance_id, user_id, username, operation_type,
                            amount, currency, exchange_rate, description)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                           """,
            operation_id,
            balance_id,
            user_id,
            username,
            op_type,
            amount,
            currency,
            exchange_rate,
            description,
        )
        return operation_id

    @classmethod
    async def get_history(cls, balance_id: int, limit: int = 10) -> List[dict]:
        results = await cls._fetch(
            """
                                   SELECT operation_id,
                                          user_id,
                                          username,
                                          operation_type,
                                          amount,
                                          currency,
                                          exchange_rate,
                                          TO_CHAR(timestamp, 'YYYY-MM-DD HH24:MI:SS') as timestamp,
                                          description
                                   FROM operations
                                   WHERE balance_id = $1
                                     AND operation_type != 'пополнение_руб_чек'
                                   ORDER BY timestamp DESC
                                   LIMIT $2
                                   """,
            balance_id,
            limit,
        )
        return [dict(row) for row in results]

    @classmethod
    async def get_operation(cls, operation_id: str) -> Optional[dict]:
        row = await cls._fetchrow(
            "SELECT * FROM operations WHERE operation_id = $1", operation_id
        )
        return dict(row) if row else None

    @classmethod
    async def delete_operation(cls, operation_id: str):
        await cls._execute(
            "DELETE FROM operations WHERE operation_id = $1", operation_id
        )
        return {
            "success": True,
            "message": "Операция удалена, баланс скорректирован",
        }

    @classmethod
    async def get_operations(cls, balance_id: Optional[int] = None) -> List[dict]:
        if balance_id is None:
            results = await cls._fetch(
                """
                                        SELECT o.operation_id,
                                               o.balance_id,
                                               b.name,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description
                                        FROM operations o
                                                 LEFT JOIN balances b ON o.balance_id = b.id
                                        ORDER BY o.timestamp DESC
                                        """
            )
        else:
            results = await cls._fetch(
                """
                                        SELECT o.operation_id,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description,
                                               b.name
                                        FROM operations o
                                                 LEFT JOIN balances b ON o.balance_id = b.id
                                        WHERE o.balance_id = $1
                                        ORDER BY o.timestamp DESC
                                        """,
                balance_id,
            )
        return [dict(row) for row in results]

    @classmethod
    async def get_operations_with_period(
        cls, balance_id: Optional[int], start_date: datetime, end_date: datetime
    ) -> List[dict]:
        if balance_id is None:
            results = await cls._fetch(
                """
                                        SELECT o.operation_id,
                                               o.balance_id,
                                               b.name,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description
                                        FROM operations o
                                                 LEFT JOIN balances b ON o.balance_id = b.id
                                        WHERE o.timestamp BETWEEN $1 AND $2
                                        ORDER BY o.timestamp DESC
                                        """,
                start_date,
                end_date,
            )
        else:
            results = await cls._fetch(
                """
                                        SELECT o.operation_id,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description,
                                               b.name
                                        FROM operations o
                                                 LEFT JOIN balances b ON o.balance_id = b.id
                                        WHERE o.balance_id = $1
                                          AND o.timestamp BETWEEN $2 AND $3
                                        ORDER BY o.timestamp DESC
                                        """,
                balance_id,
                start_date,
                end_date,
            )
        return [dict(row) for row in results]

    @classmethod
    async def get_check(cls, operation_id: str) -> Optional[dict]:
        row = await cls._fetchrow(
            """
                                   SELECT operation_id,
                                          balance_id,
                                          username,
                                          amount,
                                          currency,
                                          timestamp,
                                          description,
                                          operation_type
                                   FROM operations
                                   WHERE operation_id = $1
                                     AND operation_type = 'пополнение_руб_чек'
                                   """,
            operation_id,
        )
        return dict(row) if row else None

    @classmethod
    async def get_check_count(cls, balance_id: int) -> int:
        result = await cls._fetchval(
            """
                                      SELECT COUNT(*)
                                      FROM operations
                                      WHERE balance_id = $1
                                        AND operation_type = 'пополнение_руб_чек'
                                      """,
            balance_id,
        )
        return int(result) if result else 0

    @classmethod
    async def get_checks_by_date(
        cls, balance_id: int, start_date: datetime, end_date: datetime
    ) -> List[dict]:
        results = await cls._fetch(
            """
                                    SELECT operation_id, username, amount, timestamp, description, exchange_rate
                                    FROM operations
                                    WHERE balance_id = $1
                                      AND operation_type = 'пополнение_руб_чек'
                                      AND timestamp >= $2
                                      AND timestamp < $3
                                    ORDER BY timestamp DESC
                                    """,
            balance_id,
            start_date,
            end_date,
        )
        return [dict(row) for row in results]

    @classmethod
    async def get_all_checks_by_date(
            cls, start_date: datetime, end_date: datetime
    ) -> List[dict]:
        results = await cls._fetch(
            """
            SELECT operation_id, balance_id, username, amount, timestamp, description
            FROM operations
            WHERE operation_type = 'пополнение_руб_чек'
              AND timestamp >= $1
              AND timestamp < $2
            ORDER BY timestamp DESC
            """,
            start_date,
            end_date,
        )
        return [dict(row) for row in results]

    @classmethod
    async def get_commissions_operations(
            cls,
            balance_id: int,
            start_date: datetime | None = None,
            end_date: datetime | None = None
    ) -> float:

        query = """
                SELECT COALESCE(SUM(amount), 0)
                FROM operations
                WHERE balance_id = $1
                  AND operation_type = 'комиссия' \
                """

        params = [balance_id]

        if start_date and end_date:
            query += " AND timestamp >= $2 AND timestamp < $3"
            params.extend([start_date, end_date])

        result = await cls._fetchval(query, *params)
        return float(result)

    @classmethod
    async def update_operation(
            cls,
            operation_id: str,
            amount: float = None,
            exchange_rate: float = None,
            description: str = None,
            timestamp: datetime = None,
    ) -> bool:
        updates = []
        params = []
        param_idx = 1

        if amount is not None:
            updates.append(f"amount = ${param_idx}")
            params.append(amount)
            param_idx += 1

        if exchange_rate is not None:
            updates.append(f"exchange_rate = ${param_idx}")
            params.append(exchange_rate)
            param_idx += 1

        if description is not None:
            updates.append(f"description = ${param_idx}")
            params.append(description)
            param_idx += 1

        if timestamp is not None:
            updates.append(f"timestamp = ${param_idx}")
            params.append(timestamp)
            param_idx += 1

        if not updates:
            return False

        params.append(operation_id)
        query = f"""
                UPDATE operations
                SET {', '.join(updates)}
                WHERE operation_id = ${param_idx}
            """

        await cls._execute(query, *params)
        return True
