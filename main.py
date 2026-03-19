from __future__ import annotations

import asyncio
import logging
import signal

from pyrogram import Client, idle

from config import get_settings
from database.mongo import MongoRepository
from handlers.message_handler import ChannelRouter
from services.editor import ContentEditor
from services.sender import MessageSender


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    repository = MongoRepository(settings)
    await repository.connect()

    user_client = Client(
        name=settings.user_session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
    )
    bot_client = Client(
        name=settings.bot_session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
    )

    editor = ContentEditor()
    sender = MessageSender(bot_client=bot_client, settings=settings, editor=editor)
    router = ChannelRouter(repository=repository, sender=sender)
    router.register(user_client, bot_client)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await user_client.start()
        await bot_client.start()
        await router.refresh()
        await router.set_bot_commands(bot_client)

        logger.info("User and bot clients started successfully")
        await asyncio.gather(idle(), stop_event.wait())
        logger.info("Shutdown signal received")
    finally:
        await user_client.stop()
        await bot_client.stop()
        await repository.close()


if __name__ == "__main__":
    asyncio.run(run())
