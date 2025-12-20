"""add balances table and refactor chats

Revision ID: 23c0f8efdece
Revises: 9ac0f9a28488
Create Date: 2025-12-20 23:27:57.337644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '23c0f8efdece'
down_revision: Union[str, Sequence[str], None] = '9ac0f9a28488'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Включаем расширение для uuid (если нужно)
    2. Создаём таблицу balances с UUID PK
    3. Заполняем balances из текущих chats (по contractor_name)
    4. Добавляем chats.balance_id (UUID), связываем с balances
    5. Удаляем балансные поля из chats
    """
    # 1. Расширение для uuid (на всякий случай, в Postgres 13+ может уже быть)
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")

    # 2. Таблица balances с UUID PK
    op.execute(
        """
        CREATE TABLE balances (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name                TEXT NOT NULL UNIQUE,
            balance_rub         NUMERIC(15, 2) DEFAULT 0 NOT NULL,
            balance_usdt        NUMERIC(15, 8) DEFAULT 0 NOT NULL,
            commission_percent  NUMERIC(5, 2)  DEFAULT 0,
            is_active           BOOLEAN        DEFAULT TRUE,
            created_at          TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP      DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT balances_name_not_empty CHECK (name <> '')
        )
        """
    )

    op.execute(
        """
        CREATE INDEX idx_balances_name
            ON balances (name)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_balances_is_active
            ON balances (is_active)
        """
    )

    # 3. Заполняем balances из уникальных contractor_name
    # Один NAME → один баланс
    op.execute(
        """
        INSERT INTO balances (name, balance_rub, balance_usdt, commission_percent, created_at)
        SELECT
            contractor_name,
            SUM(balance_rub) AS total_rub,
            SUM(balance_usdt) AS total_usdt,
            MAX(commission_percent) AS commission,
            MIN(created_at) AS first_created
        FROM chats
        WHERE contractor_name IS NOT NULL AND contractor_name <> ''
        GROUP BY contractor_name
        """
    )

    # Дополнительно создаём дефолтный баланс для чатов без contractor_name
    op.execute(
        """
        INSERT INTO balances (name)
        VALUES ('__default__')
        ON CONFLICT (name) DO NOTHING
        """
    )

    # 4. Добавляем balance_id в chats и связываем
    op.execute(
        """
        ALTER TABLE chats
        ADD COLUMN balance_id UUID
        """
    )

    # Привязываем чаты с contractor_name к соответствующим балансам
    op.execute(
        """
        UPDATE chats AS c
        SET balance_id = b.id
        FROM balances AS b
        WHERE c.contractor_name = b.name
        """
    )

    # Чаты без contractor_name → на дефолтный баланс
    op.execute(
        """
        UPDATE chats
        SET balance_id = (SELECT id FROM balances WHERE name = '__default__')
        WHERE balance_id IS NULL
        """
    )

    # Делаем not null и добавляем внешний ключ
    op.execute(
        """
        ALTER TABLE chats
        ALTER COLUMN balance_id SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        ADD CONSTRAINT fk_chats_balance_id
            FOREIGN KEY (balance_id)
            REFERENCES balances (id)
            ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        CREATE INDEX idx_chats_balance_id
            ON chats (balance_id)
        """
    )

    # 5. Удаляем балансные поля из chats (теперь они живут в balances)
    op.execute(
        """
        ALTER TABLE chats
        DROP COLUMN IF EXISTS balance_rub
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        DROP COLUMN IF EXISTS balance_usdt
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        DROP COLUMN IF EXISTS commission_percent
        """
    )

    # contractor_name оставляем как "alias" имени баланса для удобства


def downgrade() -> None:
    """
    Откат:
    1. Вернуть балансные поля в chats
    2. Перенести значения из balances обратно в chats
    3. Удалить FK и balance_id
    4. Удалить balances
    """
    # 1. Возвращаем колонки в chats
    op.execute(
        """
        ALTER TABLE chats
        ADD COLUMN commission_percent NUMERIC(5, 2) DEFAULT 0
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        ADD COLUMN balance_rub NUMERIC(15, 2) DEFAULT 0
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        ADD COLUMN balance_usdt NUMERIC(15, 2) DEFAULT 0
        """
    )

    # 2. Переносим данные обратно
    op.execute(
        """
        UPDATE chats AS c
        SET
            commission_percent = b.commission_percent,
            balance_rub       = b.balance_rub,
            balance_usdt      = b.balance_usdt
        FROM balances AS b
        WHERE c.balance_id = b.id
        """
    )

    # 3. Удаляем FK и колонку balance_id
    op.execute(
        """
        ALTER TABLE chats
        DROP CONSTRAINT IF EXISTS fk_chats_balance_id
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS idx_chats_balance_id
        """
    )

    op.execute(
        """
        ALTER TABLE chats
        DROP COLUMN IF EXISTS balance_id
        """
    )

    # 4. Удаляем таблицу balances (и расширение оставить, оно не мешает)
    op.execute(
        """
        DROP TABLE IF EXISTS balances CASCADE
        """
    )

