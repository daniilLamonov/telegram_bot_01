import asyncio
import asyncpg
from datetime import datetime, timedelta
import random
from faker import Faker
from config import settings

# Инициализация Faker
fake = Faker(['ru_RU', 'en_US'])  # Русские и английские имена
Faker.seed(42)  # Для воспроизводимости результатов


async def generate_bulk_data(num_chats: int = 5, operations_per_chat: int = 1000):
    """
    Генерировать и вставить большое количество тестовых данных

    Args:
        num_chats: Количество тестовых чатов
        operations_per_chat: Количество операций на каждый чат
    """

    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)

    try:
        print(f"🚀 Начинаем генерацию {num_chats} чатов с {operations_per_chat} операциями каждый...")
        print(f"📊 Всего будет создано: {num_chats * operations_per_chat} операций\n")

        # ======= 1. Генерируем и вставляем чаты =======
        print("📝 Генерация чатов...")
        chats_data = []

        for i in range(num_chats):
            chat_id = -1000000000000 - random.randint(1000000, 9999999)
            contractor_name = fake.company()
            commission = round(random.uniform(0.5, 5.0), 2)
            balance_rub = round(random.uniform(10000, 100000), 2)
            balance_usdt = round(random.uniform(100, 1000), 2)

            chats_data.append((
                chat_id,
                contractor_name,
                commission,
                balance_rub,
                balance_usdt
            ))

        # Массовая вставка чатов
        await conn.executemany('''
                               INSERT INTO chats (chat_id, contractor_name, commission_percent, balance_rub,
                                                  balance_usdt)
                               VALUES ($1, $2, $3, $4, $5)
                               ON CONFLICT (chat_id) DO UPDATE
                                   SET contractor_name    = EXCLUDED.contractor_name,
                                       commission_percent = EXCLUDED.commission_percent,
                                       balance_rub        = EXCLUDED.balance_rub,
                                       balance_usdt       = EXCLUDED.balance_usdt
                               ''', chats_data)

        print(f"✅ Создано {len(chats_data)} чатов\n")

        # ======= 2. Генерируем операции =======
        print("📝 Генерация операций (это может занять некоторое время)...")

        operation_types = [
            ('пополнение_руб', 'RUB', 500, 50000, None, 0.4),
            ('пополнение_usdt', 'USDT', 10, 500, None, 0.15),
            ('пополнение_руб_чек', 'RUB', 1000, 30000, None, 0.2),
            ('выплата_руб', 'RUB', 500, 20000, None, 0.1),
            ('выплата_usdt', 'USDT', 10, 300, None, 0.05),
            ('обмен_руб_usdt', 'RUB', 5000, 50000, (90.0, 95.0), 0.08),
            ('комиссия', 'RUB', 10, 500, None, 0.02),
        ]

        all_operations = []

        for chat_id, contractor_name, *_ in chats_data:
            for j in range(operations_per_chat):
                # Выбираем тип операции с учетом вероятности
                weights = [item[5] for item in operation_types]
                op_type, currency, min_amt, max_amt, rate_range, _ = random.choices(
                    operation_types,
                    weights=weights
                )[0]

                # Генерируем данные
                amount = round(random.uniform(min_amt, max_amt), 2)
                user_id = random.randint(100000000, 999999999)
                username = fake.user_name()

                # Случайная дата за последние 90 дней
                days_ago = random.randint(0, 90)
                hours_ago = random.randint(0, 23)
                minutes_ago = random.randint(0, 59)
                timestamp = datetime.now() - timedelta(
                    days=days_ago,
                    hours=hours_ago,
                    minutes=minutes_ago
                )

                # Курс обмена
                exchange_rate = None
                if rate_range:
                    exchange_rate = round(random.uniform(rate_range[0], rate_range[1]), 4)

                # Генерируем уникальный operation_id
                operation_id = fake.uuid4()[:8]

                # Описание в зависимости от типа
                descriptions = {
                    'пополнение_руб': f'Пополнение наличными. Сумма: {amount:.2f} ₽',
                    'пополнение_usdt': f'Пополнение USDT. Сумма: {amount:.2f}',
                    'пополнение_руб_чек': f'Плательщик: {fake.name()}. Чек на {amount:.2f} ₽',
                    'выплата_руб': f'Выплата наличными {amount:.2f} ₽',
                    'выплата_usdt': f'Выплата {amount:.2f} USDT',
                    'обмен_руб_usdt': f'Обмен {amount:.2f} ₽ по курсу {exchange_rate}',
                    'комиссия': f'Комиссия {amount:.2f} ₽',
                }
                description = descriptions.get(op_type, f'Операция {op_type}')

                all_operations.append((
                    operation_id,
                    chat_id,
                    user_id,
                    username,
                    op_type,
                    amount,
                    currency,
                    exchange_rate,
                    timestamp,
                    description
                ))

        print(f"📊 Сгенерировано {len(all_operations)} операций")
        print("💾 Вставка в БД (используем COPY для максимальной скорости)...\n")

        # ======= 3. Массовая вставка через copy_records_to_table =======
        # Это САМЫЙ БЫСТРЫЙ способ для asyncpg!
        await conn.copy_records_to_table(
            'operations',
            records=all_operations,
            columns=[
                'operation_id', 'chat_id', 'user_id', 'username',
                'operation_type', 'amount', 'currency', 'exchange_rate',
                'timestamp', 'description'
            ]
        )

        print("✅ Все операции успешно вставлены!\n")

        # ======= 4. Статистика =======
        print("=" * 50)
        print("📊 СТАТИСТИКА")
        print("=" * 50)

        total_chats = await conn.fetchval('SELECT COUNT(*) FROM chats')
        total_operations = await conn.fetchval('SELECT COUNT(*) FROM operations')

        print(f"Всего чатов: {total_chats}")
        print(f"Всего операций: {total_operations}")

        # Статистика по типам операций
        print("\nОпераций по типам:")
        stats = await conn.fetch('''
                                 SELECT operation_type, COUNT(*) as count, SUM(amount) as total_amount
                                 FROM operations
                                 GROUP BY operation_type
                                 ORDER BY count DESC
                                 ''')

        for row in stats:
            print(f"  {row['operation_type']:25s}: {row['count']:6d} шт, сумма: {row['total_amount']:12.2f}")

        # Примеры контрагентов
        print("\nПримеры контрагентов:")
        contractors = await conn.fetch('''
                                       SELECT contractor_name, balance_rub, balance_usdt
                                       FROM chats
                                       LIMIT 5
                                       ''')

        for row in contractors:
            print(f"  {row['contractor_name']:30s} | {row['balance_rub']:10.2f} ₽ | {row['balance_usdt']:8.2f} USDT")

        print("\n🎉 Генерация завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


async def clear_all_data():
    """Очистить все данные (опционально)"""
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    try:
        print("🗑️  Очистка данных...")
        await conn.execute('TRUNCATE TABLE operations CASCADE')
        await conn.execute('TRUNCATE TABLE chats CASCADE')
        print("✅ Данные очищены")
    finally:
        await conn.close()


if __name__ == '__main__':
    import sys

    print("=" * 50)
    print("ГЕНЕРАТОР ТЕСТОВЫХ ДАННЫХ")
    print("=" * 50)
    print()

    # Параметры по умолчанию
    num_chats = 10
    operations_per_chat = 100

    # Можно передать параметры через командную строку
    if len(sys.argv) > 1:
        num_chats = int(sys.argv[1])
    if len(sys.argv) > 2:
        operations_per_chat = int(sys.argv[2])

    # Спросить про очистку
    clear = input("Очистить существующие данные? (y/N): ").lower() == 'y'

    if clear:
        asyncio.run(clear_all_data())
        print()

    # Генерация
    asyncio.run(generate_bulk_data(num_chats, operations_per_chat))
