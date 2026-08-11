"""create persistent QR settings

Revision ID: b7a8f4c2d901
Revises: ad2df988368a
Create Date: 2026-08-11 12:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7a8f4c2d901"
down_revision: Union[str, Sequence[str], None] = "ad2df988368a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE qr_settings
        (
            id          SMALLINT PRIMARY KEY,
            tab_index   SMALLINT NOT NULL DEFAULT 2,
            is_enabled  BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT qr_settings_single_row CHECK (id = 1),
            CONSTRAINT qr_settings_valid_tab CHECK (tab_index IN (2, 3, 4, 5))
        )
        """
    )
    op.execute(
        """
        INSERT INTO qr_settings (id, tab_index, is_enabled)
        VALUES (1, 2, TRUE)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS qr_settings")
