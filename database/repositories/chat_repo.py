from typing import Optional, List
from .base import BaseRepository


class ChatRepository(BaseRepository):
    """Репозиторий для работы с чатами"""

    async def get_chat(self, chat_id: int) -> Optional[dict]:
        """Получить информацию о чате"""
        row = await self._fetchrow(
            'SELECT * FROM chats WHERE chat_id = $1',
            chat_id
        )
        return dict(row) if row else None

    async def is_chat_initialized(self, chat_id: int) -> bool:
        """Проверить, инициализирован ли чат"""
        result = await self._fetchval(
            'SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1 AND is_active = true)',
            chat_id
        )
        return result or False

    async def initialize_chat(
            self,
            chat_id: int,
            chat_title: str,
            chat_type: str,
            contractor_name: str,
            initialized_by: int
    ) -> bool:
        """Инициализировать чат"""
        try:
            await self._execute('''
                                INSERT INTO chats (chat_id, chat_title, chat_type, contractor_name, initialized_by,
                                                   is_active)
                                VALUES ($1, $2, $3, $4, $5, true)
                                ON CONFLICT (chat_id)
                                    DO UPDATE SET contractor_name = EXCLUDED.contractor_name,
                                                  chat_title      = EXCLUDED.chat_title,
                                                  is_active       = true,
                                                  updated_at      = NOW()
                                ''', chat_id, chat_title, chat_type, contractor_name, initialized_by)
            return True
        except Exception as e:
            print(f"❌ Error initializing chat: {e}")
            return False

    async def get_contractor_name(self, chat_id: int) -> str:
        """Получить имя контрагента"""
        result = await self._fetchval(
            'SELECT contractor_name FROM chats WHERE chat_id = $1',
            chat_id
        )
        return result if result else "Не установлено"

    async def save_contractor_name(self, chat_id: int, contractor_name: str):
        """Сохранить имя контрагента"""
        await self._execute('''
                            INSERT INTO chats (chat_id, contractor_name)
                            VALUES ($1, $2)
                            ON CONFLICT (chat_id) DO UPDATE SET contractor_name = $2
                            ''', chat_id, contractor_name)

    async def get_commission(self, chat_id: int) -> float:
        """Получить процент комиссии"""
        result = await self._fetchval(
            'SELECT commission_percent FROM chats WHERE chat_id = $1',
            chat_id
        )
        return float(result) if result else 0.0

    async def set_commission(self, chat_id: int, percent: float) -> bool:
        """Установить процент комиссии"""
        exists = await self._fetchval(
            'SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1)',
            chat_id
        )
        if exists:
            await self._execute(
                'UPDATE chats SET commission_percent = $1 WHERE chat_id = $2',
                percent, chat_id
            )
            return True
        return False

    async def get_balance(self, chat_id: int) -> tuple[float, float]:
        """Получить баланс (RUB, USDT)"""
        result = await self._fetchrow(
            'SELECT balance_rub, balance_usdt FROM chats WHERE chat_id = $1',
            chat_id
        )
        if not result:
            return (0.0, 0.0)
        return (float(result['balance_rub']), float(result['balance_usdt']))

    async def update_balance(self, chat_id: int, balance_rub: float, balance_usdt: float):
        """Обновить баланс"""
        await self._execute('''
                            UPDATE chats
                            SET balance_rub  = $1,
                                balance_usdt = $2,
                                updated_at   = CURRENT_TIMESTAMP
                            WHERE chat_id = $3
                            ''', balance_rub, balance_usdt, chat_id)

    async def add_to_balance(self, chat_id: int, amount_rub: float, amount_usdt: float = 0.0):
        """Добавить к балансу"""
        await self._execute('''
                            UPDATE chats
                            SET balance_rub  = balance_rub + $1,
                                balance_usdt = balance_usdt + $2,
                                updated_at   = CURRENT_TIMESTAMP
                            WHERE chat_id = $3
                            ''', amount_rub, amount_usdt, chat_id)

    async def get_all_chats(self) -> List[dict]:
        """Получить все чаты"""
        results = await self._fetch('''
                                    SELECT chat_id,
                                           contractor_name,
                                           balance_rub,
                                           balance_usdt,
                                           commission_percent,
                                           created_at,
                                           updated_at
                                    FROM chats
                                    ORDER BY contractor_name
                                    ''')
        return [dict(row) for row in results]
