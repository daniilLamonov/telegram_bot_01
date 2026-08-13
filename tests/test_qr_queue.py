from unittest.mock import AsyncMock

import pytest

from services.qr_queue import (
    CLEANUP_DELAY_MS,
    CLEANUP_QUEUE,
    GENERATION_QUEUE,
    QRCleanupTask,
    QRJob,
    declare_cleanup_queues,
    declare_generation_queue,
)


def test_qr_job_round_trip():
    job = QRJob(
        job_id="job-id",
        chat_id=-100,
        command_message_id=10,
        processing_message_id=11,
        amount=15_000,
        tab_index=4,
    )

    assert QRJob.from_bytes(job.to_bytes()) == job


def test_cleanup_task_round_trip():
    task = QRCleanupTask(chat_id=-100, message_ids=(10, 11))

    assert QRCleanupTask.from_bytes(task.to_bytes()) == task


@pytest.mark.asyncio
async def test_generation_queue_is_single_active_consumer():
    channel = AsyncMock()

    await declare_generation_queue(channel)

    channel.declare_queue.assert_awaited_once_with(
        GENERATION_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-single-active-consumer": True,
        },
    )


@pytest.mark.asyncio
async def test_cleanup_delay_is_twenty_minutes_and_dead_letters():
    channel = AsyncMock()

    await declare_cleanup_queues(channel)

    assert channel.declare_queue.await_args_list[1].args == ("qr.cleanup.delay",)
    delay_options = channel.declare_queue.await_args_list[1].kwargs
    assert delay_options["durable"] is True
    assert delay_options["arguments"] == {
        "x-queue-type": "classic",
        "x-message-ttl": CLEANUP_DELAY_MS,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": CLEANUP_QUEUE,
    }
    assert CLEANUP_DELAY_MS == 20 * 60 * 1000
