# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncpg


class MockRecord(dict):
    """Имитация asyncpg.Record - ведёт себя как словарь"""

    def __getitem__(self, key):
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        return dict.get(self, key, default)


@pytest.fixture(autouse=True)
def mock_db_pool():
    """Mock database pool для всех тестов"""
    mock_pool = AsyncMock(spec=asyncpg.Pool)
    mock_conn = AsyncMock()

    # Настраиваем контекстный менеджер для pool.acquire()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None

    with patch('database.connection.get_pool', return_value=mock_pool), \
            patch('database.repositories.base.get_pool', return_value=mock_pool):
        yield mock_pool


@pytest.fixture
def bot():
    """Mock для бота"""
    bot_mock = AsyncMock()
    bot_mock.delete_message = AsyncMock()
    bot_mock.send_message = AsyncMock()
    return bot_mock


@pytest.fixture
def message():
    """Mock для сообщения"""
    mock = AsyncMock()
    mock.answer = AsyncMock(return_value=MagicMock(message_id=123))
    mock.reply = AsyncMock()
    mock.delete = AsyncMock()
    mock.edit_text = AsyncMock()

    # from_user
    mock.from_user = MagicMock()
    mock.from_user.id = 123456
    mock.from_user.username = "testuser"
    mock.from_user.full_name = "Test User"

    # chat
    mock.chat = MagicMock()
    mock.chat.id = 123456
    mock.chat.type = "group"
    mock.chat.title = "Test Chat"

    # bot
    mock.bot = AsyncMock()
    mock.bot.delete_message = AsyncMock()

    mock.text = ""
    mock.message_id = 123

    return mock


@pytest.fixture
def callback():
    """Mock для коллбэк-запроса"""
    mock = AsyncMock()
    mock.answer = AsyncMock()
    mock.message = AsyncMock()
    mock.message.answer = AsyncMock()
    mock.message.edit_text = AsyncMock()
    mock.message.delete = AsyncMock()
    mock.message.message_id = 456
    mock.data = ""

    mock.from_user = MagicMock()
    mock.from_user.id = 123456
    mock.from_user.username = "testuser"

    return mock


@pytest.fixture
def state():
    """Mock для FSM состояния"""
    mock = AsyncMock()
    mock.update_data = AsyncMock()
    mock.get_data = AsyncMock(return_value={})
    mock.set_state = AsyncMock()
    mock.clear = AsyncMock()
    mock.get_state = AsyncMock(return_value=None)
    return mock


# Хелпер для создания mock Record
def create_mock_record(**kwargs):
    """Создаёт MockRecord с заданными полями"""
    return MockRecord(kwargs)
