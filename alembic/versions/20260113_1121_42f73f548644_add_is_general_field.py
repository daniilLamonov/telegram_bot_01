"""add_is_general_field

Revision ID: 42f73f548644
Revises: 23c0f8efdece
Create Date: 2026-01-13 11:21:51.296902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42f73f548644'
down_revision: Union[str, Sequence[str], None] = '23c0f8efdece'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_general column to balances table."""
    op.add_column(
        'chats',
        sa.Column('is_general', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    """Remove is_general column from balances table."""
    op.drop_column('chats', 'is_general')
