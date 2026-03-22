from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyrogram import Client, filters
from pyrogram.errors import ChannelInvalid, ChannelPrivate, FloodWait, InviteHashExpired, InviteHashInvalid, PeerIdInvalid, UsernameNotOccupied
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from database.mongo import MongoRepository
from services.sender import MessageSender
from utils.helpers import collect_channel_keys, normalize_channel_key

logger = logging.getLogger(__name__)


class ChannelRouter:
    def __init__(self, repository: MongoRepository, sender: MessageSender) -> None:
        self.repository = repository
        self.sender = sender
        self._source_map: dict[str, dict[str, Any]] = {}

    async def refresh(self) -> list[dict[str, Any]]:
        configs = await self.repository.get_all_channels()
        logger.info("Loaded %s raw channel routing rules from MongoDB", len(configs))
        return configs

    async def _ensure_source_access(self, user_client: Client, config: dict[str, Any]) -> dict[str, Any] | None:
        source = config.get("source_channel")
        invite_link = config.get("source_invite_link")

        try:
            chat = await user_client.get_chat(source)
            logger.info("✅ Access OK: %s", source)
            return {
                "chat_id": str(chat.id),
                "username": f"@{chat.username.lower()}" if chat.username else None,
            }
        except FloodWait as exc:
            logger.warning("FloodWait while validating %s, sleeping %s seconds", source, exc.value)
            return await self._retry_get_chat(user_client, config, exc.value)
        except (PeerIdInvalid, ChannelInvalid, ChannelPrivate, UsernameNotOccupied, InviteHashInvalid, InviteHashExpired) as exc:
            logger.warning("❌ Cannot access: %s | %s", source, exc)
            if invite_link:
                return await self._attempt_join_and_resolve(user_client, source, invite_link)
            return None
        except Exception as exc:
            logger.exception("Unexpected error while validating source %s: %s", source, exc)
            return None

    async def _retry_get_chat(self, user_client: Client, config: dict[str, Any], delay: int) -> dict[str, Any] | None:
        source = config.get("source_channel")
        await asyncio.sleep(delay)
        try:
            chat = await user_client.get_chat(source)
            logger.info("✅ Access OK after retry: %s", source)
            return {
                "chat_id": str(chat.id),
                "username": f"@{chat.username.lower()}" if chat.username else None,
            }
        except Exception as exc:
            logger.warning("❌ Cannot access after retry: %s | %s", source, exc)
            return None

    async def _attempt_join_and_resolve(self, user_client: Client, source: str, invite_link: str) -> dict[str, Any] | None:
        try:
            await user_client.join_chat(invite_link)
            logger.info("Joined source channel using invite link: %s", source)
            chat = await user_client.get_chat(source)
            logger.info("✅ Access OK after join: %s", source)
            return {
                "chat_id": str(chat.id),
                "username": f"@{chat.username.lower()}" if chat.username else None,
            }
        except Exception as exc:
            logger.warning("Skipped inaccessible channel %s even after join attempt: %s", source, exc)
            return None

    async def initialize_sources(self, user_client: Client) -> None:
        configs = await self.refresh()
        source_map: dict[str, dict[str, Any]] = {}

        for config in configs:
            try:
                source = config.get("source_channel")
                normalized_source = normalize_channel_key(source)
                if not normalized_source:
                    logger.warning("Skipping channel config with empty source: %s", config)
                    continue
                if normalized_source.startswith("-100"):
                    logger.warning(
                        "Source channel %s is stored as a numeric peer id. Prefer @username for more reliable deployments.",
                        source,
                    )

                resolved = await self._ensure_source_access(user_client, config)
                if not resolved:
                    logger.warning("Skipping inaccessible source channel: %s", source)
                    continue

                source_map[normalized_source] = config
                source_map[resolved["chat_id"]] = config
                if resolved.get("username"):
                    source_map[resolved["username"]] = config
                    source_map[resolved["username"].lstrip("@")] = config
            except Exception as exc:
                logger.exception("Failed to initialize source config safely: %s", exc)

        self._source_map = source_map
        logger.info("Initialized %s accessible source channel keys", len(self._source_map))

    def _match(self, message: Message) -> dict[str, Any] | None:
        for key in collect_channel_keys(message.chat.id, message.chat.username):
            config = self._source_map.get(key)
            if config:
                return config
        return None

    async def handle_channel_post(self, client: Client, message: Message) -> None:
        try:
            config = self._match(message)
            if not config:
                logger.debug("Skipping message %s from unconfigured source %s", message.id, message.chat.id)
                return

            source_channel = config.get("source_channel")
            destination_channel = config.get("destination_channel")
            logger.info("📤 %s → %s | msg_id=%s", source_channel, destination_channel, message.id)
            await self.sender.send_processed_message(config, message)
        except Exception as exc:
            logger.exception("Failed to process message %s safely: %s", getattr(message, "id", "unknown"), exc)

    def register(self, user_client: Client) -> None:
        user_client.add_handler(MessageHandler(self.handle_channel_post, filters.channel))
