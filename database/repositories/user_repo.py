from typing import Optional
from .base import BaseRepository


class UserRepository(BaseRepository):
    """Репозиторий для работы с пользователями бота"""

    async def get_user(self, user_id: int) -> Optional[dict]:
        """Получить пользователя по ID"""
        row = await self._fetchrow(
            "SELECT * FROM users WHERE user_id = $1",
            user_id
        )
        return dict(row) if row else None

    async def create_or_update_user(
            self,
            user_id: int,
            username: Optional[str],
            first_name: Optional[str],
            last_name: Optional[str]
    ) -> dict:
        """Создать или обновить пользователя"""
        row = await self._fetchrow(
            """
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id)
                DO UPDATE SET username   = EXCLUDED.username,
                              first_name = EXCLUDED.first_name,
                              last_name  = EXCLUDED.last_name,
                              updated_at = NOW()
            RETURNING *
            """,
            user_id, username, first_name, last_name
        )
        return dict(row)

    async def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь админом"""
        result = await self._fetchval(
            "SELECT is_admin FROM users WHERE user_id = $1",
            user_id
        )
        return result or False

    async def set_admin(self, user_id: int, is_admin: bool = True):
        """Назначить/снять права админа"""
        await self._execute(
            "UPDATE users SET is_admin = $1, updated_at = NOW() WHERE user_id = $2",
            is_admin, user_id
        )
