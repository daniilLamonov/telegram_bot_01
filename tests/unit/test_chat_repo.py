# tests/unit/test_chat_repo.py
import pytest
from tests.conftest import create_mock_record


class TestChatRepo:
    """Тесты для ChatRepo"""

    @pytest.mark.asyncio
    async def test_get_chat_returns_chat_data_when_found(self, monkeypatch):
        """get_chat возвращает данные чата, если найден"""
        from database.repositories.chat_repo import ChatRepo

        # Arrange
        chat_id = 123
        expected_data = create_mock_record(
            chat_id=chat_id,
            chat_title='Test Chat',
            chat_type='group',
            is_active=True,
            initialized_by=456,
            balance_id='balance-123',
            balance_name='Test Balance',
            balance_rub=100.0,
            balance_usdt=1.0,
            commission_percent=0.0
        )

        async def mock_fetchrow(query, *args):
            return expected_data

        monkeypatch.setattr(ChatRepo, '_fetchrow', staticmethod(mock_fetchrow))

        # Act
        result = await ChatRepo.get_chat(chat_id)

        # Assert
        assert result is not None
        assert result['chat_id'] == chat_id
        assert result['chat_title'] == 'Test Chat'

    @pytest.mark.asyncio
    async def test_get_chat_returns_none_when_not_found(self, monkeypatch):
        """get_chat возвращает None, если чат не найден"""
        from database.repositories.chat_repo import ChatRepo

        # Arrange
        async def mock_fetchrow(query, *args):
            return None

        monkeypatch.setattr(ChatRepo, '_fetchrow', staticmethod(mock_fetchrow))

        # Act
        result = await ChatRepo.get_chat(999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_is_chat_initialized_returns_true_for_active_chat(self, monkeypatch):
        """is_chat_initialized возвращает True для активного чата"""
        from database.repositories.chat_repo import ChatRepo

        # Arrange
        async def mock_fetchval(query, *args):
            return True

        monkeypatch.setattr(ChatRepo, '_fetchval', staticmethod(mock_fetchval))

        # Act
        result = await ChatRepo.is_chat_initialized(123)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_is_chat_initialized_returns_false_when_not_found(self, monkeypatch):
        """is_chat_initialized возвращает False, если чат не найден"""
        from database.repositories.chat_repo import ChatRepo

        # Arrange
        async def mock_fetchval(query, *args):
            return None

        monkeypatch.setattr(ChatRepo, '_fetchval', staticmethod(mock_fetchval))

        # Act
        result = await ChatRepo.is_chat_initialized(999)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_chat_inserts_new_chat(self, monkeypatch):
        """initialize_chat создаёт новый чат"""
        from database.repositories.chat_repo import ChatRepo

        # Arrange
        executed = False

        async def mock_execute(query, *args):
            nonlocal executed
            executed = True

        monkeypatch.setattr(ChatRepo, '_execute', staticmethod(mock_execute))

        # Act
        result = await ChatRepo.initialize_chat(
            chat_id=123,
            chat_title='New Chat',
            chat_type='group',
            initialized_by=456,
            balance_id='balance-123'
        )

        # Assert
        assert result is True
        assert executed is True
