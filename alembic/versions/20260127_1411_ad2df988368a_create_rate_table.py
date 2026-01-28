"""create rate table

Revision ID: ad2df988368a
Revises: 42f73f548644
Create Date: 2026-01-27 14:11:30.936898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad2df988368a'
down_revision: Union[str, Sequence[str], None] = '42f73f548644'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'rate',
        sa.Column('exchange_date', sa.Date(), nullable=False, primary_key=True),
        sa.Column('rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False),
        sa.PrimaryKeyConstraint('exchange_date', name='pk_rate')
    )

    op.create_index(
        'idx_rate_exchange_date',
        'rate',
        ['exchange_date'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_rate_exchange_date', table_name='rate')
    op.drop_table('rate')
