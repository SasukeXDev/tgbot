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
        self._recent_messages: set[tuple[str, int]] = set()

    async def _validate_destination(self, destination: Any, source_channel: Any) -> str | None:
        normalized = normalize_channel_key(destination)
        if not normalized or not is_valid_channel(normalized):
            logger.error("❌ Skipping invalid destination: %s | source=%s", destination, source_channel)
            return None

        try:
            await self.bot_client.get_chat(normalized)
            return normalized
        except (PeerIdInvalid, ChannelInvalid, ChannelPrivate, ChatAdminRequired, UsernameInvalid, UsernameNotOccupied) as exc:
            logger.error("❌ Cannot access %s: %s", normalized, exc)
            return None
        except Exception as exc:
            logger.exception(
                "Unexpected destination resolution failure | source=%s | destination=%s | error=%s",
                source_channel,
                normalized,
                exc,
            )
            return None

    async def _safe_send(
        self,
        send_callable: Callable[[], Awaitable[Message]],
        *,
        delay: float,
        source_channel: Any,
        destination: str,
        inbound_message_id: int,
    ) -> Message | None:
        attempts = 0
        while attempts < 3:
            try:
                attempts += 1
                async with self._send_semaphore:
                    result = await send_callable()
                    logger.info(
                        "✅ success | source=%s | destination=%s | inbound_msg_id=%s | outbound_msg_id=%s",
                        source_channel,
                        destination,
                        inbound_message_id,
                        result.id,
                    )
                    if delay > 0:
                        await asyncio.sleep(delay)
                    return result
            except FloodWait as exc:
                logger.warning(
                    "⚠️ FloodWait | source=%s | destination=%s | inbound_msg_id=%s | sleep=%s | attempt=%s",
                    source_channel,
                    destination,
                    inbound_message_id,
                    exc.value,
                    attempts,
                )
                await asyncio.sleep(exc.value)
            except (ChannelInvalid, ChannelPrivate, ChatAdminRequired, PeerIdInvalid, UsernameInvalid, UsernameNotOccupied) as exc:
                logger.error(
                    "❌ fail | source=%s | destination=%s | inbound_msg_id=%s | error=%s",
                    source_channel,
                    destination,
                    inbound_message_id,
                    exc,
                )
                return None
            except Exception as exc:
                logger.exception(
                    "❌ fail | source=%s | destination=%s | inbound_msg_id=%s | attempt=%s | error=%s",
                    source_channel,
                    destination,
                    inbound_message_id,
                    attempts,
                    exc,
                )
                if attempts >= 3:
                    return None
                await asyncio.sleep(1)
        return None

    def _is_duplicate(self, source_channel: Any, message_id: int) -> bool:
        key = (str(source_channel), message_id)
        if key in self._recent_messages:
            logger.info("Skipping duplicate message | source=%s | msg_id=%s", source_channel, message_id)
            return True
        self._recent_messages.add(key)
        if len(self._recent_messages) > 1000:
            self._recent_messages = set(list(self._recent_messages)[-500:])
        return False

    async def send_processed_message(self, config: dict[str, Any], message: Message) -> Message | None:
        try:
            source_channel = config.get("source_channel", message.chat.id)
            if self._is_duplicate(source_channel, message.id):
                return None

            destination = await self._validate_destination(config.get("destination_channel"), source_channel)
            if not destination:
                return None

            edit_settings = config.get("edit_settings") or config.get("edit_options") or {}
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
                    inbound_message_id=message.id,
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
                    inbound_message_id=message.id,
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
                    inbound_message_id=message.id,
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
                    inbound_message_id=message.id,
                )

            logger.info("Skipping unsupported or empty message %s from %s", message.id, source_channel)
            return None
        except Exception as exc:
            logger.exception("❌ Error: %s", exc)
            return None
