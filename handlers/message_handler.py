from __future__ import annotations

import logging
from typing import Any

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import BotCommand, Message

from database.mongo import MongoRepository
from services.sender import MessageSender
from utils.helpers import collect_channel_keys, normalize_channel_key

logger = logging.getLogger(__name__)


class ChannelRouter:
    def __init__(self, repository: MongoRepository, sender: MessageSender) -> None:
        self.repository = repository
        self.sender = sender
        self._source_map: dict[str, dict[str, Any]] = {}

    async def refresh(self) -> None:
        configs = await self.repository.get_all_channels()
        source_map: dict[str, dict[str, Any]] = {}
        for config in configs:
            key = normalize_channel_key(config.get("source_channel"))
            if key:
                source_map[key] = config
        self._source_map = source_map
        logger.info("Loaded %s channel routing rules", len(self._source_map))

    def _match(self, message: Message) -> dict[str, Any] | None:
        for key in collect_channel_keys(message.chat.id, message.chat.username):
            config = self._source_map.get(key)
            if config:
                return config
        return None

    async def handle_channel_post(self, _: Client, message: Message) -> None:
        config = self._match(message)
        if not config:
            return
        logger.info(
            "Routing message %s from source %s to destination %s",
            message.id,
            config.get("source_channel"),
            config.get("destination_channel"),
        )
        await self.sender.send_processed_message(config, message)

    async def add_channel_command(self, client: Client, message: Message) -> None:
        args = message.text.split(maxsplit=3)
        if len(args) < 3:
            await message.reply_text("Usage: /add_channel <source> <destination> [prefix]")
            return

        source, destination = args[1], args[2]
        prefix = args[3] if len(args) == 4 else ""
        payload = {
            "source_channel": source,
            "destination_channel": destination,
            "edit_settings": {
                "prefix": prefix,
                "suffix": "",
                "replace_words": {},
                "remove_links": False,
                "remove_hashtags": False,
            },
            "buttons": [],
            "delay": 0,
        }
        await self.repository.add_channel(payload)
        await self.refresh()
        await message.reply_text(f"Added routing from {source} to {destination}")

    async def remove_channel_command(self, client: Client, message: Message) -> None:
        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            await message.reply_text("Usage: /remove_channel <source>")
            return
        deleted = await self.repository.remove_channel(args[1])
        await self.refresh()
        if deleted:
            await message.reply_text(f"Removed routing for {args[1]}")
        else:
            await message.reply_text(f"No routing found for {args[1]}")

    async def list_channels_command(self, client: Client, message: Message) -> None:
        configs = await self.repository.get_all_channels()
        if not configs:
            await message.reply_text("No channels configured.")
            return
        lines = [
            f"• {item['source_channel']} ➜ {item['destination_channel']}"
            for item in configs
        ]
        await message.reply_text("Configured channels:\n" + "\n".join(lines))

    async def set_bot_commands(self, bot_client: Client) -> None:
        commands = [
            BotCommand("add_channel", "Add a channel route"),
            BotCommand("remove_channel", "Remove a channel route"),
            BotCommand("list_channels", "List configured routes"),
        ]
        await bot_client.set_bot_commands(commands)

    def register(self, user_client: Client, bot_client: Client) -> None:
        user_client.add_handler(MessageHandler(self.handle_channel_post, filters.channel))
        bot_client.add_handler(MessageHandler(self.add_channel_command, filters.command("add_channel") & filters.private))
        bot_client.add_handler(MessageHandler(self.remove_channel_command, filters.command("remove_channel") & filters.private))
        bot_client.add_handler(MessageHandler(self.list_channels_command, filters.command("list_channels") & filters.private))
