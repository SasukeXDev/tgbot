from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired, FloodWait, PeerIdInvalid
from pyrogram.types import Message

from config import Settings
from services.editor import ContentEditor
from utils.helpers import build_reply_markup

logger = logging.getLogger(__name__)


class MessageSender:
    def __init__(self, bot_client: Client, settings: Settings, editor: ContentEditor) -> None:
        self.bot_client = bot_client
        self.settings = settings
        self.editor = editor
        self._send_semaphore = asyncio.Semaphore(settings.max_concurrent_sends)

    async def _safe_send(self, send_callable, *, delay: float) -> Message | None:
        while True:
            try:
                async with self._send_semaphore:
                    result = await send_callable()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    return result
            except FloodWait as exc:
                logger.warning("FloodWait triggered, sleeping for %s seconds", exc.value)
                await asyncio.sleep(exc.value)
            except (ChannelInvalid, ChannelPrivate, ChatAdminRequired, PeerIdInvalid) as exc:
                logger.error("Failed to send because destination is unavailable: %s", exc)
                return None

    async def send_processed_message(self, config: dict[str, Any], message: Message) -> Message | None:
        edit_settings = config.get("edit_settings", {})
        destination = config["destination_channel"]
        delay = float(config.get("delay", self.settings.default_send_delay) or 0)
        reply_markup = build_reply_markup(config.get("buttons"))

        text_source = message.text or message.caption
        entities = message.entities or message.caption_entities
        edited = self.editor.edit(text_source, entities, edit_settings)

        if message.photo:
            return await self._safe_send(
                lambda: self.bot_client.send_photo(
                    chat_id=destination,
                    photo=message.photo.file_id,
                    caption=edited.text,
                    caption_entities=edited.entities,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.DEFAULT,
                ),
                delay=delay,
            )

        if message.video:
            return await self._safe_send(
                lambda: self.bot_client.send_video(
                    chat_id=destination,
                    video=message.video.file_id,
                    caption=edited.text,
                    caption_entities=edited.entities,
                    duration=message.video.duration,
                    width=message.video.width,
                    height=message.video.height,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.DEFAULT,
                ),
                delay=delay,
            )

        if message.document:
            return await self._safe_send(
                lambda: self.bot_client.send_document(
                    chat_id=destination,
                    document=message.document.file_id,
                    caption=edited.text,
                    caption_entities=edited.entities,
                    file_name=message.document.file_name,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.DEFAULT,
                ),
                delay=delay,
            )

        if edited.text:
            return await self._safe_send(
                lambda: self.bot_client.send_message(
                    chat_id=destination,
                    text=edited.text,
                    entities=edited.entities,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.DEFAULT,
                ),
                delay=delay,
            )

        logger.info("Skipping unsupported or empty message %s from %s", message.id, message.chat.id)
        return None
