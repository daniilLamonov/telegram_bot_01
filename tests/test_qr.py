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
    monkeypatch.setattr(qr.asyncio, "to_thread", generate_in_thread)

    await qr.cmd_new(message)

    generate_in_thread.assert_awaited_once_with(qr.generate_qr, 15_000)
    processing_message.edit_media.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("amount", ["2 499", "150 001"])
async def test_qr_command_rejects_amount_outside_allowed_range(monkeypatch, amount):
    message = SimpleNamespace(text=f"/qr {amount}", answer=AsyncMock())
    send_temporary_message = AsyncMock()
    monkeypatch.setattr(qr, "delete_message", AsyncMock())
    monkeypatch.setattr(qr, "temp_msg", send_temporary_message)

    await qr.cmd_new(message)

    message.answer.assert_not_awaited()
    send_temporary_message.assert_awaited_once_with(
        message,
        "❌ Сумма должна быть от 2 500 до 150 000",
    )
