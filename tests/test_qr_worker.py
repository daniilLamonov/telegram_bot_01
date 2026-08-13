import asyncio
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call

import pytest

import qr_worker
from services.qr_queue import QRCleanupTask, QRJob
from utils.generate_qr import AuthenticationError, SiteUnavailableError


class MessageProcessContext(AbstractAsyncContextManager):
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


def incoming_message(body: bytes):
    return SimpleNamespace(
        body=body,
        process=MagicMock(return_value=MessageProcessContext()),
    )


def make_job() -> QRJob:
    return QRJob(
        job_id="job-id",
        chat_id=-100,
        command_message_id=10,
        processing_message_id=11,
        amount=15_000,
        tab_index=2,
    )


@pytest.mark.asyncio
async def test_worker_consumes_only_one_generation_at_a_time(monkeypatch):
    generation_queue = SimpleNamespace(consume=AsyncMock())
    delay_queue = SimpleNamespace()
    cleanup_queue = SimpleNamespace(consume=AsyncMock())
    generation_channel = SimpleNamespace(
        set_qos=AsyncMock(),
        declare_queue=AsyncMock(return_value=generation_queue),
    )
    cleanup_channel = SimpleNamespace(
        set_qos=AsyncMock(),
        declare_queue=AsyncMock(side_effect=[cleanup_queue, delay_queue]),
    )
    connection = SimpleNamespace(
        channel=AsyncMock(side_effect=[generation_channel, cleanup_channel])
    )
    queue_client = SimpleNamespace(connection=connection)
    worker = qr_worker.QRWorker(AsyncMock(), queue_client)
    cancelled_future = asyncio.get_running_loop().create_future()
    cancelled_future.cancel()
    monkeypatch.setattr(qr_worker.asyncio, "Future", lambda: cancelled_future)

    with pytest.raises(asyncio.CancelledError):
        await worker.run()

    generation_channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    generation_queue.consume.assert_awaited_once_with(
        worker.process_job,
        no_ack=False,
    )


@pytest.mark.asyncio
async def test_worker_retries_generation_once(monkeypatch):
    generator = MagicMock(
        side_effect=[
            SiteUnavailableError("temporary"),
            (b"qr-image", "QR data"),
        ]
    )
    monkeypatch.setattr(qr_worker, "generate_qr", generator)
    monkeypatch.setattr(qr_worker.asyncio, "sleep", AsyncMock())
    worker = qr_worker.QRWorker(AsyncMock(), AsyncMock())
    job = make_job()

    result = await worker.generate_with_retry(job)

    assert result == (b"qr-image", "QR data")
    assert generator.call_count == 2
    assert job.attempt == 1


@pytest.mark.asyncio
async def test_worker_does_not_retry_authentication_error(monkeypatch):
    generator = MagicMock(side_effect=AuthenticationError("invalid credentials"))
    monkeypatch.setattr(qr_worker, "generate_qr", generator)
    monkeypatch.setattr(qr_worker.asyncio, "sleep", AsyncMock())
    worker = qr_worker.QRWorker(AsyncMock(), AsyncMock())

    with pytest.raises(AuthenticationError):
        await worker.generate_with_retry(make_job())

    assert generator.call_count == 1


@pytest.mark.asyncio
async def test_worker_stops_after_one_retry(monkeypatch):
    generator = MagicMock(side_effect=SiteUnavailableError("temporary"))
    monkeypatch.setattr(qr_worker, "generate_qr", generator)
    monkeypatch.setattr(qr_worker.asyncio, "sleep", AsyncMock())
    worker = qr_worker.QRWorker(AsyncMock(), AsyncMock())

    with pytest.raises(SiteUnavailableError):
        await worker.generate_with_retry(make_job())

    assert generator.call_count == 2


@pytest.mark.asyncio
async def test_worker_edits_result_and_schedules_both_messages(monkeypatch):
    bot = SimpleNamespace(edit_message_media=AsyncMock())
    queue_client = SimpleNamespace(publish_cleanup=AsyncMock())
    worker = qr_worker.QRWorker(bot, queue_client)
    monkeypatch.setattr(
        worker,
        "generate_with_retry",
        AsyncMock(return_value=(b"qr-image", "QR data")),
    )
    job = make_job()

    await worker.process_job(incoming_message(job.to_bytes()))

    bot.edit_message_media.assert_awaited_once()
    queue_client.publish_cleanup.assert_awaited_once_with(
        QRCleanupTask(chat_id=-100, message_ids=(10, 11))
    )


@pytest.mark.asyncio
async def test_cleanup_deletes_all_messages():
    bot = SimpleNamespace(delete_message=AsyncMock())
    worker = qr_worker.QRWorker(bot, AsyncMock())
    task = QRCleanupTask(chat_id=-100, message_ids=(10, 11))

    await worker.process_cleanup(incoming_message(task.to_bytes()))

    assert bot.delete_message.await_args_list == [
        call(chat_id=-100, message_id=10),
        call(chat_id=-100, message_id=11),
    ]
