from database.repositories.base import BaseRepository


class QRSettingsRepo(BaseRepository):
    """Persistent global settings for QR generation."""

    DEFAULT_TAB_INDEX = 2
    ALLOWED_TAB_INDEXES = frozenset(range(1, 7))

    @classmethod
    async def get_settings(cls) -> tuple[int, bool]:
        row = await cls._fetchrow(
            "SELECT tab_index, is_enabled FROM qr_settings WHERE id = 1"
        )
        if not row:
            return cls.DEFAULT_TAB_INDEX, True
        return int(row["tab_index"]), bool(row["is_enabled"])

    @classmethod
    async def set_tab_index(cls, tab_index: int) -> None:
        if tab_index not in cls.ALLOWED_TAB_INDEXES:
            raise ValueError(f"Unsupported QR tab index: {tab_index}")

        await cls._execute(
            """
            INSERT INTO qr_settings (id, tab_index, is_enabled)
            VALUES (1, $1, TRUE)
            ON CONFLICT (id)
            DO UPDATE SET tab_index = EXCLUDED.tab_index,
                          updated_at = CURRENT_TIMESTAMP
            """,
            tab_index,
        )

    @classmethod
    async def set_enabled(cls, is_enabled: bool) -> None:
        await cls._execute(
            """
            INSERT INTO qr_settings (id, tab_index, is_enabled)
            VALUES (1, $1, $2)
            ON CONFLICT (id)
            DO UPDATE SET is_enabled = EXCLUDED.is_enabled,
                          updated_at = CURRENT_TIMESTAMP
            """,
            cls.DEFAULT_TAB_INDEX,
            is_enabled,
        )
