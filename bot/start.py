import logging

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from dishka.integrations.aiogram import setup_dishka

from bot.config import settings
from bot.di import create_container
from bot.handlers.context import set_state_service
from bot.service import NotificationService, ScheduleService, StateService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    asyncio.run(run())


async def run() -> None:
    """Start the bot."""
    from bot import setup
    from bot.handlers.notification import notification_worker

    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    container = create_container()

    setup_dishka(container=container, router=dispatcher)

    await setup.setup(dispatcher)

    async with container() as request_container:
        notification_service = await request_container.get(NotificationService)
        schedule_service = await request_container.get(ScheduleService)
        state_service = await request_container.get(StateService)

    set_state_service(state_service)

    worker_task = asyncio.create_task(
        notification_worker(bot, notification_service, schedule_service)
    )

    try:
        await dispatcher.start_polling(bot)
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await container.close()
