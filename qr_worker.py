import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
)
from aiogram.types import BufferedInputFile, InputMediaPhoto
from aio_pika.abc import AbstractIncomingMessage

from config import settings
from services.qr_queue import (
    QRCleanupTask,
    QRJob,
    QRQueueClient,
    declare_cleanup_queues,
    declare_generation_queue,
)
from utils.generate_qr import (
    AuthenticationError,
    QRGenerationError,
    SiteUnavailableError,
    generate_qr,
)
from utils.keyboards import get_delete_keyboard


logger = logging.getLogger(__name__)
RETRY_DELAY_SECONDS = 2


class QRWorker:
    def __init__(self, bot: Bot, queue_client: QRQueueClient) -> None:
        self.bot = bot
        self.queue_client = queue_client

    async def run(self) -> None:
        if self.queue_client.connection is None:
            raise RuntimeError("RabbitMQ connection is not initialized")

        generation_channel = await self.queue_client.connection.channel()
        await generation_channel.set_qos(prefetch_count=1)
        generation_queue = await declare_generation_queue(generation_channel)

        cleanup_channel = await self.queue_client.connection.channel()
        await cleanup_channel.set_qos(prefetch_count=10)
        _, cleanup_queue = await declare_cleanup_queues(cleanup_channel)

        await generation_queue.consume(self.process_job, no_ack=False)
        await cleanup_queue.consume(self.process_cleanup, no_ack=False)
        logger.info("QR worker запущен")
        await asyncio.Future()

    async def process_job(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=True):
            try:
                job = QRJob.from_bytes(message.body)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error("Некорректное QR-задание: %s", exc)
                return

            logger.info(
                "Обработка QR job_id=%s amount=%s tab_index=%s attempt=%s",
                job.job_id,
                job.amount,
                job.tab_index,
                job.attempt,
            )

            try:
                qr_bytes, data = await self.generate_with_retry(job)
            except AuthenticationError:
                await self._edit_error(
                    job,
                    "❌ Не удалось авторизоваться у агента",
                )
            except SiteUnavailableError:
                await self._edit_error(job, "❌ Сайт агента недоступен")
            except QRGenerationError as exc:
                await self._edit_error(job, f"❌ {exc}")
            except Exception:
                logger.exception("Неизвестная ошибка генерации job_id=%s", job.job_id)
                await self._edit_error(job, "❌ Произошла неизвестная ошибка")
            else:
                await self._edit_result(job, qr_bytes, data)

            await self.queue_client.publish_cleanup(
                QRCleanupTask(
                    chat_id=job.chat_id,
                    message_ids=(
                        job.command_message_id,
                        job.processing_message_id,
                    ),
                )
            )
            logger.info("QR-задание завершено job_id=%s", job.job_id)

    async def generate_with_retry(self, job: QRJob) -> tuple[bytes, str]:
        while True:
            try:
                return await asyncio.to_thread(
                    generate_qr,
                    job.amount,
                    job.tab_index,
                )
            except AuthenticationError:
                raise
            except Exception:
                if job.attempt >= 1:
                    raise
                job.attempt += 1
                logger.warning(
                    "Повтор QR job_id=%s через %s сек.",
                    job.job_id,
                    RETRY_DELAY_SECONDS,
                    exc_info=True,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    async def _edit_result(self, job: QRJob, qr_bytes: bytes, data: str) -> None:
        try:
            await self.bot.edit_message_media(
                chat_id=job.chat_id,
                message_id=job.processing_message_id,
                media=InputMediaPhoto(
                    media=BufferedInputFile(qr_bytes, filename="qr.png"),
                    caption=data,
                ),
                reply_markup=get_delete_keyboard(),
            )
        except TelegramBadRequest as exc:
            logger.info(
                "Сообщение QR уже недоступно job_id=%s: %s",
                job.job_id,
                exc,
            )

    async def _edit_error(self, job: QRJob, text: str) -> None:
        try:
            await self.bot.edit_message_text(
                text=text,
                chat_id=job.chat_id,
                message_id=job.processing_message_id,
                reply_markup=get_delete_keyboard(),
            )
        except TelegramBadRequest as exc:
            logger.info(
                "Сообщение ошибки уже недоступно job_id=%s: %s",
                job.job_id,
                exc,
            )

    async def process_cleanup(self, message: AbstractIncomingMessage) -> None:
        async with message.process(requeue=True):
            try:
                task = QRCleanupTask.from_bytes(message.body)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error("Некорректное cleanup-задание: %s", exc)
                return

            for message_id in task.message_ids:
                try:
                    await self.bot.delete_message(
                        chat_id=task.chat_id,
                        message_id=message_id,
                    )
                except (TelegramBadRequest, TelegramForbiddenError):
                    logger.debug(
                        "Сообщение уже удалено chat_id=%s message_id=%s",
                        task.chat_id,
                        message_id,
                    )
                except TelegramNetworkError:
                    raise


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    queue_client = QRQueueClient()

    try:
        await queue_client.connect()
        await QRWorker(bot, queue_client).run()
    finally:
        await queue_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
