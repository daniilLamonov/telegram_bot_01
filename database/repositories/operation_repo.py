import uuid
from typing import Optional, List
from datetime import datetime
from .base import BaseRepository


class OperationRepository(BaseRepository):
    """Репозиторий для работы с операциями"""

    async def log_operation(
            self,
            chat_id: int,
            user_id: int,
            username: str,
            op_type: str,
            amount: float,
            currency: str,
            exchange_rate: Optional[float] = None,
            description: str = ''
    ) -> str:
        """Записать операцию"""
        operation_id = str(uuid.uuid4())[:8]
        await self._execute('''
                            INSERT INTO operations
                            (operation_id, chat_id, user_id, username, operation_type,
                             amount, currency, exchange_rate, description)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            ''', operation_id, chat_id, user_id, username, op_type,
                            amount, currency, exchange_rate, description)
        return operation_id

    async def get_operation(self, operation_id: str) -> Optional[dict]:
        """Получить операцию по ID"""
        row = await self._fetchrow(
            'SELECT * FROM operations WHERE operation_id = $1',
            operation_id
        )
        return dict(row) if row else None

    async def delete_operation(self, operation_id: str):
        """Удалить операцию"""
        await self._execute(
            'DELETE FROM operations WHERE operation_id = $1',
            operation_id
        )

    async def get_history(self, chat_id: int, limit: int = 10) -> List[dict]:
        """Получить историю операций"""
        results = await self._fetch('''
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
                                    WHERE chat_id = $1
                                      AND operation_type != 'пополнение_руб_чек'
                                    ORDER BY timestamp DESC
                                    LIMIT $2
                                    ''', chat_id, limit)
        return [dict(row) for row in results]

    async def get_operations(self, chat_id: Optional[int] = None) -> List[dict]:
        """Получить все операции (опционально по чату)"""
        if chat_id is None:
            results = await self._fetch('''
                                        SELECT o.operation_id,
                                               o.chat_id,
                                               c.contractor_name,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description
                                        FROM operations o
                                                 LEFT JOIN chats c ON o.chat_id = c.chat_id
                                        ORDER BY o.timestamp DESC
                                        ''')
        else:
            results = await self._fetch('''
                                        SELECT o.operation_id,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description,
                                               c.contractor_name
                                        FROM operations o
                                                 LEFT JOIN chats c ON o.chat_id = c.chat_id
                                        WHERE o.chat_id = $1
                                        ORDER BY o.timestamp DESC
                                        ''', chat_id)
        return [dict(row) for row in results]

    async def get_operations_with_period(
            self,
            chat_id: Optional[int],
            start_date: datetime,
            end_date: datetime
    ) -> List[dict]:
        """Получить операции за период"""
        if chat_id is None:
            results = await self._fetch('''
                                        SELECT o.operation_id,
                                               o.chat_id,
                                               c.contractor_name,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description
                                        FROM operations o
                                                 LEFT JOIN chats c ON o.chat_id = c.chat_id
                                        WHERE o.timestamp BETWEEN $1 AND $2
                                        ORDER BY o.timestamp DESC
                                        ''', start_date, end_date)
        else:
            results = await self._fetch('''
                                        SELECT o.operation_id,
                                               o.user_id,
                                               o.username,
                                               o.operation_type,
                                               o.amount,
                                               o.currency,
                                               o.exchange_rate,
                                               o.timestamp,
                                               o.description,
                                               c.contractor_name
                                        FROM operations o
                                                 LEFT JOIN chats c ON o.chat_id = c.chat_id
                                        WHERE o.chat_id = $1
                                          AND o.timestamp BETWEEN $2 AND $3
                                        ORDER BY o.timestamp DESC
                                        ''', chat_id, start_date, end_date)
        return [dict(row) for row in results]

    async def get_check(self, operation_id: str) -> Optional[dict]:
        """Получить чек по ID"""
        row = await self._fetchrow('''
                                   SELECT operation_id,
                                          chat_id,
                                          username,
                                          amount,
                                          currency,
                                          timestamp,
                                          description,
                                          operation_type
                                   FROM operations
                                   WHERE operation_id = $1
                                     AND operation_type = 'пополнение_руб_чек'
                                   ''', operation_id)
        return dict(row) if row else None

    async def get_check_count(self, chat_id: int) -> int:
        """Получить количество чеков"""
        result = await self._fetchval('''
                                      SELECT COUNT(*)
                                      FROM operations
                                      WHERE chat_id = $1
                                        AND operation_type = 'пополнение_руб_чек'
                                      ''', chat_id)
        return int(result) if result else 0

    async def get_checks_by_date(
            self,
            chat_id: int,
            start_date: datetime,
            end_date: datetime
    ) -> List[dict]:
        """Получить чеки за период"""
        results = await self._fetch('''
                                    SELECT operation_id, username, amount, timestamp, description
                                    FROM operations
                                    WHERE chat_id = $1
                                      AND operation_type = 'пополнение_руб_чек'
                                      AND timestamp >= $2
                                      AND timestamp < $3
                                    ORDER BY timestamp DESC
                                    ''', chat_id, start_date, end_date)
        return [dict(row) for row in results]
