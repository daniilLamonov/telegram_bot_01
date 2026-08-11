from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Chat, Message, User

from database.repositories import UserRepo
from filters.admin import IsAdminFilter
from middlewares import chat_init_check
from middlewares.chat_init_check import ChatInitMiddleware
from utils import permissions


def make_message(*, user_id: int, chat_type: str, text: str) -> Message:
    return Message.model_construct(
        message_id=1,
        date=0,
        chat=Chat.model_construct(id=-100, type=chat_type),
        from_user=User.model_construct(
            id=user_id,
            is_bot=False,
            first_name="Test user",
        ),
        text=text,
    )


@pytest.mark.asyncio
async def test_super_admin_has_admin_access_without_database_record(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=False)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)

    assert await permissions.has_admin_access(100) is True
    database_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_admin_has_admin_access(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=True)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)

    assert await permissions.has_admin_access(200) is True
    database_check.assert_awaited_once_with(200)


@pytest.mark.asyncio
async def test_admin_filter_accepts_super_admin_without_database_record(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=False)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)
    message = SimpleNamespace(from_user=SimpleNamespace(id=100))

    assert await IsAdminFilter()(message) is True
    database_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_filter_accepts_database_admin(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=True)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)
    message = SimpleNamespace(from_user=SimpleNamespace(id=200))

    assert await IsAdminFilter()(message) is True
    database_check.assert_awaited_once_with(200)


@pytest.mark.asyncio
async def test_uninitialized_chat_allows_init_for_super_admin(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=False)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)

    handler = AsyncMock(return_value="handled")
    message = make_message(
        user_id=100,
        chat_type="group",
        text="/init Test contractor",
    )

    result = await ChatInitMiddleware()(handler, message, {})

    assert result == "handled"
    handler.assert_awaited_once_with(message, {})
    database_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_uninitialized_chat_allows_init_for_database_admin(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    database_check = AsyncMock(return_value=True)
    monkeypatch.setattr(UserRepo, "is_admin", database_check)

    handler = AsyncMock(return_value="handled")
    message = make_message(
        user_id=200,
        chat_type="group",
        text="/init Test contractor",
    )

    result = await ChatInitMiddleware()(handler, message, {})

    assert result == "handled"
    handler.assert_awaited_once_with(message, {})
    database_check.assert_awaited_once_with(200)


@pytest.mark.asyncio
async def test_uninitialized_chat_blocks_non_admin(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    monkeypatch.setattr(UserRepo, "is_admin", AsyncMock(return_value=False))
    chat_initialized = AsyncMock(return_value=False)
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(chat_init_check.ChatRepo, "is_chat_initialized", chat_initialized)
    monkeypatch.setattr(chat_init_check, "temp_msg", send_temporary_message)

    handler = AsyncMock()
    message = make_message(
        user_id=200,
        chat_type="group",
        text="/check 100 Test user",
    )

    result = await ChatInitMiddleware()(handler, message, {})

    assert result is None
    handler.assert_not_awaited()
    chat_initialized.assert_awaited_once_with(-100)
    send_temporary_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_private_chat_stays_blocked_for_super_admin(monkeypatch):
    monkeypatch.setattr(permissions.settings, "SUPER_ADMIN_ID", [100])
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(chat_init_check, "temp_msg", send_temporary_message)

    handler = AsyncMock()
    message = make_message(user_id=100, chat_type="private", text="/init Test")

    result = await ChatInitMiddleware()(handler, message, {})

    assert result is None
    handler.assert_not_awaited()
    send_temporary_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_set_admin_creates_or_updates_user(monkeypatch):
    execute = AsyncMock()
    monkeypatch.setattr(UserRepo, "_execute", execute)

    await UserRepo.set_admin(200, is_admin=True)

    query, user_id, is_admin = execute.await_args.args
    assert "INSERT INTO users (user_id, is_admin)" in query
    assert "ON CONFLICT (user_id)" in query
    assert (user_id, is_admin) == (200, True)
