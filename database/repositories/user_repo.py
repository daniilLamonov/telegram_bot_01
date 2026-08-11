from typing import Optional
from .base import BaseRepository


class UserRepo(BaseRepository):

    @classmethod
    async def get_user(cls, user_id: int) -> Optional[dict]:
        row = await cls._fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None

    @classmethod
    async def create_or_update_user(
        cls,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        last_name: Optional[str],
    ) -> dict:
        row = await cls._fetchrow(
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
            user_id,
            username,
            first_name,
            last_name,
        )
        return dict(row)

    @classmethod
    async def is_admin(cls, user_id: int) -> bool:
        result = await cls._fetchval(
            "SELECT is_admin FROM users WHERE user_id = $1", user_id
        )
        return result or False

    @classmethod
    async def set_admin(cls, user_id: int, is_admin: bool = True):
        await cls._execute(
            """
            INSERT INTO users (user_id, is_admin)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
                DO UPDATE SET is_admin = EXCLUDED.is_admin,
                              updated_at = NOW()
            """,
            user_id,
            is_admin,
        )
