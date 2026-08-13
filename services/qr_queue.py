import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import aio_pika
from aio_pika import DeliveryMode, Message
from aio_pika.abc import (
    AbstractRobustChannel,
    AbstractRobustConnection,
    AbstractRobustQueue,
)

from config import settings


GENERATION_QUEUE = "qr.generate"
CLEANUP_DELAY_QUEUE = "qr.cleanup.delay"
CLEANUP_QUEUE = "qr.cleanup"
CLEANUP_DELAY_MS = 20 * 60 * 1000
PUBLISH_TIMEOUT_SECONDS = 10


@dataclass(slots=True)
class QRJob:
    job_id: str
    chat_id: int
    command_message_id: int
    processing_message_id: int
    amount: int
    tab_index: int
    attempt: int = 0

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":")).encode()

    @classmethod
    def from_bytes(cls, body: bytes) -> "QRJob":
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("QR job must be a JSON object")
        return cls(**data)


@dataclass(slots=True)
class QRCleanupTask:
    chat_id: int
    message_ids: tuple[int, ...]

    def to_bytes(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":")).encode()

    @classmethod
    def from_bytes(cls, body: bytes) -> "QRCleanupTask":
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("QR cleanup task must be a JSON object")
        message_ids = data.get("message_ids")
        if not isinstance(message_ids, list):
            raise ValueError("message_ids must be a list")
        return cls(
            chat_id=int(data["chat_id"]),
            message_ids=tuple(int(message_id) for message_id in message_ids),
        )


async def declare_generation_queue(
    channel: AbstractRobustChannel,
) -> AbstractRobustQueue:
    return await channel.declare_queue(
        GENERATION_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-single-active-consumer": True,
        },
    )


async def declare_cleanup_queues(
    channel: AbstractRobustChannel,
) -> tuple[AbstractRobustQueue, AbstractRobustQueue]:
    cleanup_queue = await channel.declare_queue(
        CLEANUP_QUEUE,
        durable=True,
        arguments={"x-queue-type": "classic"},
    )
    delay_queue = await channel.declare_queue(
        CLEANUP_DELAY_QUEUE,
        durable=True,
        arguments={
            "x-queue-type": "classic",
            "x-message-ttl": CLEANUP_DELAY_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": CLEANUP_QUEUE,
        },
    )
    return delay_queue, cleanup_queue


class QRQueueClient:
    def __init__(self) -> None:
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractRobustChannel | None = None
        self._connect_lock = asyncio.Lock()
        self._publish_lock = asyncio.Lock()

    async def connect(self) -> None:
        async with self._connect_lock:
            if (
                self.connection
                and not self.connection.is_closed
                and self.channel
                and not self.channel.is_closed
            ):
                return

            if self.connection and not self.connection.is_closed:
                await self.connection.close()

            connection = await aio_pika.connect_robust(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                login=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASSWORD.get_secret_value(),
                virtualhost=settings.RABBITMQ_VHOST,
                timeout=PUBLISH_TIMEOUT_SECONDS,
            )
            try:
                channel = await connection.channel(
                    publisher_confirms=True,
                    on_return_raises=True,
                )
                await declare_generation_queue(channel)
                await declare_cleanup_queues(channel)
            except Exception:
                await connection.close()
                raise

            self.connection = connection
            self.channel = channel

    async def publish_job(self, job: QRJob) -> None:
        await self.connect()
        await self._publish(
            routing_key=GENERATION_QUEUE,
            body=job.to_bytes(),
            message_id=job.job_id,
            message_type="qr.generate",
        )

    async def publish_cleanup(self, task: QRCleanupTask) -> None:
        await self.connect()
        await self._publish(
            routing_key=CLEANUP_DELAY_QUEUE,
            body=task.to_bytes(),
            message_type="qr.cleanup",
        )

    async def _publish(
        self,
        *,
        routing_key: str,
        body: bytes,
        message_type: str,
        message_id: str | None = None,
    ) -> None:
        if not self.channel or self.channel.is_closed:
            raise RuntimeError("RabbitMQ channel is not available")

        message = Message(
            body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message_id,
            timestamp=datetime.now(timezone.utc),
            type=message_type,
        )
        async with self._publish_lock:
            await asyncio.wait_for(
                self.channel.default_exchange.publish(
                    message,
                    routing_key=routing_key,
                    mandatory=True,
                ),
                timeout=PUBLISH_TIMEOUT_SECONDS,
            )

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()


_client: QRQueueClient | None = None


async def init_qr_queue() -> QRQueueClient:
    global _client
    client = QRQueueClient()
    _client = client
    await client.connect()
    return client


def get_qr_queue() -> QRQueueClient:
    if _client is None:
        raise RuntimeError("QR queue is not initialized")
    return _client


async def close_qr_queue() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
