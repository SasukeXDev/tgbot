from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired, FloodWait, PeerIdInvalid, UsernameInvalid, UsernameNotOccupied
from pyrogram.types import Message

from config import Settings
from services.editor import ContentEditor
from utils.helpers import build_reply_markup, is_valid_channel, normalize_channel_key

logger = logging.getLogger(__name__)


class MessageSender:
    def __init__(self, bot_client: Client, settings: Settings, editor: ContentEditor) -> None:
        self.bot_client = bot_client
        self.settings = settings
        self.editor = editor
        self._send_semaphore = asyncio.Semaphore(settings.max_concurrent_sends)

    async def _validate_destination(self, destination: Any, source_channel: Any) -> str | None:
        normalized = normalize_channel_key(destination)
        if not normalized:
            logger.error("❌ Invalid destination for source %s: %s", source_channel, destination)
            return None
        if normalized == "<destination>":
            logger.warning("⚠️ Skipping placeholder destination for source %s", source_channel)
            return None
        if not is_valid_channel(normalized):
            logger.error("❌ Invalid destination format for source %s: %s", source_channel, destination)
            return None

        try:
            await self.bot_client.get_chat(normalized)
            logger.info("Destination access OK | source=%s | destination=%s", source_channel, normalized)
            return normalized
        except (PeerIdInvalid, ChannelInvalid, ChannelPrivate, ChatAdminRequired, UsernameInvalid, UsernameNotOccupied) as exc:
            logger.error("❌ Cannot access destination %s for source %s: %s", normalized, source_channel, exc)
            return None
        except Exception as exc:
            logger.exception("Unexpected destination resolution failure | source=%s | destination=%s | error=%s", source_channel, normalized, exc)
            return None

    async def _safe_send(
        self,
        send_callable: Callable[[], Awaitable[Message]],
        *,
        delay: float,
        source_channel: Any,
        destination: str,
    ) -> Message | None:
        while True:
            try:
                async with self._send_semaphore:
                    result = await send_callable()
                    logger.info("✅ Send success | source=%s | destination=%s | message_id=%s", source_channel, destination, result.id)
                    if delay > 0:
                        await asyncio.sleep(delay)
                    return result
            except FloodWait as exc:
                logger.warning("FloodWait triggered | source=%s | destination=%s | sleep=%s", source_channel, destination, exc.value)
                await asyncio.sleep(exc.value)
            except (ChannelInvalid, ChannelPrivate, ChatAdminRequired, PeerIdInvalid, UsernameInvalid, UsernameNotOccupied) as exc:
                logger.error("❌ Send failed due to invalid destination | source=%s | destination=%s | error=%s", source_channel, destination, exc)
                return None
            except Exception as exc:
                logger.exception("❌ Send failed | source=%s | destination=%s | error=%s", source_channel, destination, exc)
                return None

    async def send_processed_message(self, config: dict[str, Any], message: Message) -> Message | None:
        source_channel = config.get("source_channel", message.chat.id)
        destination = await self._validate_destination(config.get("destination_channel"), source_channel)
        if not destination:
            return None

        edit_settings = config.get("edit_settings", {})
        delay = float(config.get("delay", self.settings.default_send_delay) or 0)
        reply_markup = build_reply_markup(config.get("buttons"))

        logger.info("Preparing outbound message | source=%s | destination=%s | incoming_message=%s", source_channel, destination, message.id)

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
                source_channel=source_channel,
                destination=destination,
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
                source_channel=source_channel,
                destination=destination,
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
                source_channel=source_channel,
                destination=destination,
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
                source_channel=source_channel,
                destination=destination,
            )

        logger.info("Skipping unsupported or empty message %s from %s", message.id, source_channel)
        return None
