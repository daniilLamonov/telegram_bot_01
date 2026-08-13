from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import qr


def make_message(text: str = "/qr 15 000"):
    processing_message = SimpleNamespace(
        message_id=200,
        edit_text=AsyncMock(),
    )
    bot = SimpleNamespace(delete_message=AsyncMock())
    message = SimpleNamespace(
        text=text,
        message_id=100,
        chat=SimpleNamespace(id=-1000),
        from_user=SimpleNamespace(id=100),
        bot=bot,
        answer=AsyncMock(return_value=processing_message),
    )
    return message, processing_message


@pytest.mark.asyncio
async def test_qr_command_publishes_job_with_selected_tab(monkeypatch):
    message, processing_message = make_message()
    queue_client = SimpleNamespace(
        publish_job=AsyncMock(),
        publish_cleanup=AsyncMock(),
    )
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(4, True)),
    )
    monkeypatch.setattr(qr, "get_qr_queue", lambda: queue_client)
    monkeypatch.setattr(qr, "uuid4", lambda: "job-id")

    await qr.cmd_new(message)

    queue_client.publish_job.assert_awaited_once()
    job = queue_client.publish_job.await_args.args[0]
    assert job.job_id == "job-id"
    assert job.chat_id == -1000
    assert job.command_message_id == 100
    assert job.processing_message_id == 200
    assert job.amount == 15_000
    assert job.tab_index == 4
    processing_message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["2 499", "150 001"])
async def test_qr_command_rejects_amount_outside_allowed_range(monkeypatch, amount):
    message, _ = make_message(f"/qr {amount}")
    queue_client = SimpleNamespace(
        publish_job=AsyncMock(),
        publish_cleanup=AsyncMock(),
    )
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(2, True)),
    )
    monkeypatch.setattr(qr, "get_qr_queue", lambda: queue_client)
    monkeypatch.setattr(qr, "temp_msg", send_temporary_message)

    await qr.cmd_new(message)

    message.answer.assert_not_awaited()
    queue_client.publish_job.assert_not_awaited()
    queue_client.publish_cleanup.assert_awaited_once()
    cleanup = queue_client.publish_cleanup.await_args.args[0]
    assert cleanup.message_ids == (100,)
    send_temporary_message.assert_awaited_once_with(
        message,
        "❌ Сумма должна быть от 2 500 до 150 000",
    )


@pytest.mark.asyncio
async def test_qr_command_is_blocked_when_disabled(monkeypatch):
    message, _ = make_message()
    queue_client = SimpleNamespace(
        publish_job=AsyncMock(),
        publish_cleanup=AsyncMock(),
    )
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(4, False)),
    )
    monkeypatch.setattr(qr, "get_qr_queue", lambda: queue_client)
    monkeypatch.setattr(qr, "temp_msg", send_temporary_message)

    await qr.cmd_new(message)

    queue_client.publish_job.assert_not_awaited()
    queue_client.publish_cleanup.assert_awaited_once()
    send_temporary_message.assert_awaited_once_with(message, "Временно выключено")


@pytest.mark.asyncio
async def test_qr_command_handles_unavailable_queue(monkeypatch):
    message, processing_message = make_message()
    queue_client = SimpleNamespace(
        publish_job=AsyncMock(side_effect=RuntimeError("RabbitMQ unavailable")),
    )
    local_cleanup = MagicMock()
    monkeypatch.setattr(
        qr.QRSettingsRepo,
        "get_settings",
        AsyncMock(return_value=(2, True)),
    )
    monkeypatch.setattr(qr, "get_qr_queue", lambda: queue_client)
    monkeypatch.setattr(qr, "schedule_local_cleanup", local_cleanup)

    await qr.cmd_new(message)

    processing_message.edit_text.assert_awaited_once()
    assert processing_message.edit_text.await_args.args[0] == (
        "❌ Очередь QR временно недоступна"
    )
    local_cleanup.assert_called_once_with(message, (100, 200))


@pytest.mark.asyncio
async def test_local_cleanup_deletes_each_message(monkeypatch):
    message, _ = make_message()
    monkeypatch.setattr(qr.asyncio, "sleep", AsyncMock())

    await qr.delete_messages_later(
        bot=message.bot,
        chat_id=message.chat.id,
        message_ids=(100, 200),
    )

    assert message.bot.delete_message.await_count == 2


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
