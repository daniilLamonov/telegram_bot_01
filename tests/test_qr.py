from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from handlers import qr


@pytest.mark.asyncio
async def test_qr_command_removes_spaces_from_amount(monkeypatch):
    processing_message = SimpleNamespace(edit_media=AsyncMock())
    message = SimpleNamespace(
        text="/qr 15 000",
        answer=AsyncMock(return_value=processing_message),
    )
    generate_in_thread = AsyncMock(return_value=(b"qr-image", "QR data"))
    monkeypatch.setattr(qr, "delete_message", AsyncMock())
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(2, True)),
    )
    monkeypatch.setattr(qr.asyncio, "to_thread", generate_in_thread)

    await qr.cmd_new(message)

    generate_in_thread.assert_awaited_once_with(qr.generate_qr, 15_000, 2)
    processing_message.edit_media.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["2 499", "150 001"])
async def test_qr_command_rejects_amount_outside_allowed_range(monkeypatch, amount):
    message = SimpleNamespace(text=f"/qr {amount}", answer=AsyncMock())
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(qr, "delete_message", AsyncMock())
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(2, True)),
    )
    monkeypatch.setattr(qr, "temp_msg", send_temporary_message)

    await qr.cmd_new(message)

    message.answer.assert_not_awaited()
    send_temporary_message.assert_awaited_once_with(
        message,
        "❌ Сумма должна быть от 2 500 до 150 000",
    )


@pytest.mark.asyncio
async def test_qr_command_is_blocked_when_disabled(monkeypatch):
    message = SimpleNamespace(text="/qr 15 000")
    send_temporary_message = AsyncMock()
    generate_in_thread = AsyncMock()
    monkeypatch.setattr(qr, "delete_message", AsyncMock())
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(4, False)),
    )
    monkeypatch.setattr(qr, "temp_msg", send_temporary_message)
    monkeypatch.setattr(qr.asyncio, "to_thread", generate_in_thread)

    await qr.cmd_new(message)

    send_temporary_message.assert_awaited_once_with(message, "Временно выключено")
    generate_in_thread.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_qr_mode_persists_selected_tab(monkeypatch):
    callback_message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(
        data="set_qr_mode:5",
        from_user=SimpleNamespace(id=100),
        message=callback_message,
        answer=AsyncMock(),
    )
    set_tab_index = AsyncMock()
    monkeypatch.setattr(qr, "is_super_admin", lambda _user_id: True)
    monkeypatch.setattr(qr.QRSettingsRepo, "set_tab_index", set_tab_index)

    await qr.set_qr_mode(callback)

    set_tab_index.assert_awaited_once_with(5)
    callback_message.edit_text.assert_awaited_once_with("✅ Р/С выбран: РОСДОР")


@pytest.mark.asyncio
async def test_set_qr_command_shows_all_modes(monkeypatch):
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=100),
        answer=AsyncMock(),
    )
    monkeypatch.setattr(qr, "is_super_admin", lambda _user_id: True)
    monkeypatch.setattr(qr, "delete_message", AsyncMock())

    await qr.cmd_set_qr(message)

    message.answer.assert_awaited_once()
    call = message.answer.await_args
    assert call.args == ("Выберите Р/С:",)
    buttons = [
        (button.text, button.callback_data)
        for row in call.kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert buttons == [
        ("СГБ", "set_qr_mode:2"),
        ("РАЙФ", "set_qr_mode:4"),
        ("РОСДОР", "set_qr_mode:5"),
        ("КУБАНЬ", "set_qr_mode:3"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler", "enabled"),
    [(qr.cmd_stop_qr, False), (qr.cmd_start_qr, True)],
)
async def test_super_admin_can_toggle_qr(monkeypatch, handler, enabled):
    message = SimpleNamespace(from_user=SimpleNamespace(id=100))
    set_enabled = AsyncMock()
    monkeypatch.setattr(qr, "is_super_admin", lambda _user_id: True)
    monkeypatch.setattr(qr, "delete_message", AsyncMock())
    monkeypatch.setattr(qr, "temp_msg", AsyncMock())
    monkeypatch.setattr(qr.QRSettingsRepo, "set_enabled", set_enabled)

    await handler(message)

    set_enabled.assert_awaited_once_with(enabled)
