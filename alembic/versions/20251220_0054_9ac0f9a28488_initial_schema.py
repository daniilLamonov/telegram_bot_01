"""initial schema

Revision ID: 9ac0f9a28488
Revises: 
Create Date: 2025-12-20 00:54:41.487922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ac0f9a28488'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chats
        (
            chat_id            BIGINT PRIMARY KEY,
            contractor_name    TEXT NOT NULL,
            commission_percent NUMERIC(5, 2)  DEFAULT 0,
            balance_rub        NUMERIC(15, 2) DEFAULT 0,
            balance_usdt       NUMERIC(15, 2) DEFAULT 0,
            chat_title         TEXT,
            chat_type          TEXT,
            is_active          BOOLEAN        DEFAULT true,
            initialized_by     BIGINT,
            created_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            updated_at         TIMESTAMP      DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chats_is_active
            ON chats (chat_id, is_active)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operations
        (
            id             SERIAL PRIMARY KEY,
            operation_id   TEXT UNIQUE    NOT NULL,
            chat_id        BIGINT         NOT NULL,
            user_id        BIGINT         NOT NULL,
            username       TEXT,
            operation_type TEXT           NOT NULL,
            amount         NUMERIC(15, 2) NOT NULL,
            currency       TEXT           NOT NULL,
            exchange_rate  NUMERIC(15, 4),
            timestamp      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description    TEXT
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operations_chat
            ON operations (chat_id)
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operations_timestamp
            ON operations (timestamp DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users
        (
            user_id    BIGINT PRIMARY KEY,
            username   VARCHAR(255),
            first_name VARCHAR(255),
            last_name  VARCHAR(255),
            is_admin   BOOLEAN   DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_users_is_admin
            ON users (is_admin)
        """
    )


def downgrade() -> None:
    """Откат - удаление таблиц"""
    op.execute("DROP TABLE IF EXISTS chats CASCADE")
    op.execute("DROP TABLE IF EXISTS operations CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")