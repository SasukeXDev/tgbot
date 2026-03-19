from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
import sys
from typing import Any

import uvicorn
from fastapi import FastAPI
from pyrogram import Client

from config import get_settings
from database.mongo import MongoRepository
from handlers.message_handler import ChannelRouter
from services.editor import ContentEditor
from services.sender import MessageSender

print("Python Version:", sys.version)

app = FastAPI(title="Telegram Automation Service")


@app.get("/")
async def home() -> dict[str, str]:
    return {"status": "Bot is running"}


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def init_channels(user_client: Client, router: ChannelRouter) -> None:
    """Resolve configured source chats at startup and skip invalid peers without crashing."""
    await router.initialize_sources(user_client)


async def start_bot(shutdown_event: asyncio.Event) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    repository = MongoRepository(settings)
    await repository.connect()

    user_client = Client(
        settings.user_session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        session_string=settings.session_string,
    )
    bot_client = Client(
        settings.bot_session_name,
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
    )

    editor = ContentEditor()
    sender = MessageSender(bot_client=bot_client, settings=settings, editor=editor)
    router = ChannelRouter(repository=repository, sender=sender)
    router.register(user_client, bot_client)

    try:
        await user_client.start()
        await bot_client.start()
        await init_channels(user_client, router)
        await router.set_bot_commands(bot_client)
        logger.info("Telegram automation bot started in background task")
        await shutdown_event.wait()
    finally:
        with contextlib.suppress(Exception):
            await user_client.stop()
        with contextlib.suppress(Exception):
            await bot_client.stop()
        await repository.close()


async def main() -> None:
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, shutdown_event.set)

    bot_task = asyncio.create_task(start_bot(shutdown_event), name="telegram-bot")
    port = int(os.environ.get("PORT", 10000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        shutdown_event.set()
        with contextlib.suppress(Exception):
            await bot_task


if __name__ == "__main__":
    asyncio.run(main())
