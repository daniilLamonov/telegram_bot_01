"""add balances table, link chats and operations to balances

Revision ID: 23c0f8efdece
Revises: 9ac0f9a28488
Create Date: 2025-12-20 23:27:57.337644
"""
from typing import Sequence, Union

from alembic import op


revision: str = "23c0f8efdece"
down_revision: Union[str, Sequence[str], None] = "9ac0f9a28488"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Включаем расширение uuid-ossp
    2. Создаём таблицу balances с UUID PK
    3. Наполняем balances из chats (по contractor_name)
    4. Добавляем chats.balance_id (UUID) и связываем с balances
    5. Удаляем balance_rub/balance_usdt/commission_percent из chats
    6. Добавляем operations.balance_id (UUID) и заполняем через chats
    7. Удаляем chat_id из operations
    """
    # 1. Расширение для uuid
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 2. Таблица balances
    op.execute(
        """
        CREATE TABLE balances (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name                TEXT NOT NULL UNIQUE,
            balance_rub         NUMERIC(15, 2) DEFAULT 0 NOT NULL,
            balance_usdt        NUMERIC(15, 2) DEFAULT 0 NOT NULL,
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

    # 3. Наполняем balances из chats: один contractor_name → один баланс
    op.execute(
        """
        INSERT INTO balances (name, balance_rub, balance_usdt, commission_percent, created_at)
        SELECT
            contractor_name,
            SUM(balance_rub)         AS total_rub,
            SUM(balance_usdt)        AS total_usdt,
            MAX(commission_percent)  AS commission,
            MIN(created_at)          AS first_created
        FROM chats
        WHERE contractor_name IS NOT NULL
          AND contractor_name <> ''
        GROUP BY contractor_name
        """
    )

    # дефолтный баланс для чатов без contractor_name (фолбек)
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

    # Привязка по contractor_name
    op.execute(
        """
        UPDATE chats AS c
        SET balance_id = b.id
        FROM balances AS b
        WHERE c.contractor_name = b.name
        """
    )

    # Чаты без имени контрагента отправляем на дефолтный баланс
    op.execute(
        """
        UPDATE chats
        SET balance_id = (SELECT id FROM balances WHERE name = '__default__')
        WHERE balance_id IS NULL
        """
    )

    # NOT NULL + FK + индекс
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

    # 5. Удаляем балансные поля из chats (они теперь в balances)
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

    # contractor_name оставляем для удобства отображения

    # 6. Добавляем balance_id в operations и заполняем через chats
    op.execute(
        """
        ALTER TABLE operations
        ADD COLUMN balance_id UUID
        """
    )

    op.execute(
        """
        UPDATE operations AS o
        SET balance_id = c.balance_id
        FROM chats AS c
        WHERE o.chat_id = c.chat_id
        """
    )

    op.execute(
        """
        UPDATE operations
        SET balance_id = (SELECT id FROM balances WHERE name = '__default__')
        WHERE balance_id IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE operations
        ALTER COLUMN balance_id SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE operations
        ADD CONSTRAINT fk_operations_balance_id
            FOREIGN KEY (balance_id)
            REFERENCES balances (id)
            ON DELETE RESTRICT
        """
    )

    op.execute(
        """
        CREATE INDEX idx_operations_balance_id
            ON operations (balance_id)
        """
    )

    # 7. Удаляем chat_id из operations
    op.execute(
        """
        ALTER TABLE operations
        DROP COLUMN IF EXISTS chat_id
        """
    )


def downgrade() -> None:
    """
    Откат:
    1. Вернуть chat_id в operations (пустой, без восстановления данных)
    2. Удалить FK и колонку balance_id из operations
    3. Вернуть балансные поля в chats
    4. Перенести значения из balances обратно в chats
    5. Удалить FK и balance_id из chats
    6. Удалить balances
    """
    # 1. operations: возвращаем chat_id, чтобы схема совпала с прошлой
    op.execute(
        """
        ALTER TABLE operations
        ADD COLUMN chat_id BIGINT
        """
    )

    # 2. operations: снимаем FK + индекс и удаляем balance_id
    op.execute(
        """
        ALTER TABLE operations
        DROP CONSTRAINT IF EXISTS fk_operations_balance_id
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS idx_operations_balance_id
        """
    )

    op.execute(
        """
        ALTER TABLE operations
        DROP COLUMN IF EXISTS balance_id
        """
    )

    # 3. chats: возвращаем балансные поля
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

    # 4. Переносим значения из balances обратно в chats
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

    # 5. Удаляем FK/индекс и колонку balance_id из chats
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

    # 6. Удаляем balances
    op.execute(
        """
        DROP TABLE IF EXISTS balances CASCADE
        """
    )
