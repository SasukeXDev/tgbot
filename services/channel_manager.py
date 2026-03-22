from __future__ import annotations

import logging
from typing import Any

from pyrogram import Client

from database.mongo import MongoRepository
from utils.helpers import is_placeholder_value, is_valid_channel, normalize_channel_key

logger = logging.getLogger(__name__)


class ChannelManager:
    def __init__(self, repository: MongoRepository, user_client: Client, bot_client: Client) -> None:
        self.repository = repository
        self.user_client = user_client
        self.bot_client = bot_client

    async def _validate_with_telegram(self, client: Client, channel: str, role: str) -> tuple[bool, str | None]:
        try:
            await client.get_chat(channel)
            return True, None
        except Exception as exc:
            logger.warning("Telegram validation failed | role=%s | channel=%s | error=%s", role, channel, exc)
            return False, f"❌ Invalid {role}: {exc}"

    async def validate_channel(self, channel: Any, *, role: str, client: Client) -> tuple[bool, str, str | None]:
        normalized = normalize_channel_key(channel)
        if not normalized or is_placeholder_value(normalized):
            return False, "", f"❌ Invalid {role}. Placeholders like <destination> are not allowed."

        if not is_valid_channel(normalized):
            return False, "", f"❌ Invalid {role} format. Use @username or -100id"

        ok, error = await self._validate_with_telegram(client, normalized, role)
        if not ok:
            return False, "", error
        return True, normalized, None

    async def add_channel(
        self,
        source_channel: Any,
        destination_channel: Any,
        *,
        filters: dict[str, Any] | None = None,
        edit_options: dict[str, Any] | None = None,
        edit_settings: dict[str, Any] | None = None,
        source_invite_link: str | None = None,
    ) -> tuple[bool, str]:
        valid_source, normalized_source, source_error = await self.validate_channel(
            source_channel,
            role="source channel",
            client=self.user_client,
        )
        if not valid_source:
            return False, source_error or "❌ Invalid source channel"

        valid_destination, normalized_destination, destination_error = await self.validate_channel(
            destination_channel,
            role="destination channel",
            client=self.bot_client,
        )
        if not valid_destination:
            return False, destination_error or "❌ Invalid destination channel"

        payload = {
            "source_channel": normalized_source,
            "destination_channel": normalized_destination,
            "filters": filters or {},
            "edit_options": edit_options or {},
            "edit_settings": edit_settings or {},
            "source_invite_link": source_invite_link,
        }

        await self.repository.add_channel(payload)
        logger.info(
            "Saved channel mapping | source=%s | destination=%s",
            normalized_source,
            normalized_destination,
        )
        return True, f"✅ Added mapping: {normalized_source} → {normalized_destination}"

    async def remove_channel(self, source_channel: Any) -> tuple[bool, str]:
        normalized_source = normalize_channel_key(source_channel)
        if not normalized_source or is_placeholder_value(normalized_source):
            return False, "❌ Invalid source channel."

        deleted = await self.repository.remove_channel(normalized_source)
        if not deleted:
            return False, f"❌ No routing found for {normalized_source}"

        logger.info("Removed channel mapping | source=%s", normalized_source)
        return True, f"✅ Removed routing for {normalized_source}"

    async def list_channels(self) -> list[dict[str, Any]]:
        configs = await self.repository.get_all_channels()
        unique_configs: list[dict[str, Any]] = []
        seen_sources: set[str] = set()

        for config in configs:
            source = normalize_channel_key(config.get("source_channel"))
            if not source or source in seen_sources:
                continue
            seen_sources.add(source)
            unique_configs.append(config)

        return unique_configs
