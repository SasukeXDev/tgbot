from __future__ import annotations

import logging
from typing import Awaitable, Callable

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import BotCommand, Message

from services.channel_manager import ChannelManager

logger = logging.getLogger(__name__)

HELP_TEXT = """📌 Available Commands:\n\n/add_channel\n→ Add source & destination channel\n\n/remove_channel\n→ Remove existing mapping\n\n/list_channels\n→ Show all mappings\n\n/status\n→ Bot status\n\n/help\n→ Show this help message"""
START_TEXT = """👋 Welcome to the Telegram forwarding bot.\n\nUse /add_channel to create a source → destination route, /list_channels to review mappings, and /remove_channel to delete one.\n\nSend /help any time for the full command list."""


class CommandHandlerService:
    def __init__(self, manager: ChannelManager, on_routes_changed: Callable[[], Awaitable[None]]) -> None:
        self.manager = manager
        self.on_routes_changed = on_routes_changed

    async def start_command(self, client: Client, message: Message) -> None:
        try:
            await message.reply_text(START_TEXT)
        except Exception as exc:
            logger.exception("Failed to serve /start: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def help_command(self, client: Client, message: Message) -> None:
        try:
            await message.reply_text(HELP_TEXT)
        except Exception as exc:
            logger.exception("Failed to serve /help: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def status_command(self, client: Client, message: Message) -> None:
        try:
            routes = await self.manager.list_channels()
            await message.reply_text(
                f"✅ Bot is running\nConfigured routes: {len(routes)}\nMode: userbot listener + bot sender"
            )
        except Exception as exc:
            logger.exception("Failed to serve /status: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def add_channel_command(self, client: Client, message: Message) -> None:
        try:
            args = (message.text or "").split()
            if len(args) != 3:
                await message.reply_text("Usage: /add_channel <source> <destination>")
                return

            source, destination = args[1], args[2]
            ok, result = await self.manager.add_channel(
                source,
                destination,
                filters={},
                edit_options={},
                edit_settings={},
            )
            if ok:
                await self.on_routes_changed()
            await message.reply_text(result)
        except Exception as exc:
            logger.exception("Failed to handle /add_channel: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def remove_channel_command(self, client: Client, message: Message) -> None:
        try:
            args = (message.text or "").split(maxsplit=1)
            if len(args) != 2:
                await message.reply_text("Usage: /remove_channel <source>")
                return

            ok, result = await self.manager.remove_channel(args[1])
            if ok:
                await self.on_routes_changed()
            await message.reply_text(result)
        except Exception as exc:
            logger.exception("Failed to handle /remove_channel: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def list_channels_command(self, client: Client, message: Message) -> None:
        try:
            configs = await self.manager.list_channels()
            if not configs:
                await message.reply_text("No channels configured.")
                return

            lines = [
                f"• {item['source_channel']} → {item['destination_channel']}"
                for item in configs
            ]
            await message.reply_text("Configured channels:\n" + "\n".join(lines))
        except Exception as exc:
            logger.exception("Failed to handle /list_channels: %s", exc)
            await message.reply_text(f"❌ Error: {str(exc)}")

    async def set_bot_commands(self, bot_client: Client) -> None:
        commands = [
            BotCommand("start", "Welcome and usage guide"),
            BotCommand("help", "Show help and commands"),
            BotCommand("add_channel", "Add a channel route"),
            BotCommand("remove_channel", "Remove a channel route"),
            BotCommand("list_channels", "List configured routes"),
            BotCommand("status", "Show bot status"),
        ]
        await bot_client.set_bot_commands(commands)

    def register(self, bot_client: Client) -> None:
        private_commands = filters.private
        bot_client.add_handler(MessageHandler(self.start_command, filters.command("start") & private_commands))
        bot_client.add_handler(MessageHandler(self.help_command, filters.command("help") & private_commands))
        bot_client.add_handler(MessageHandler(self.status_command, filters.command("status") & private_commands))
        bot_client.add_handler(MessageHandler(self.add_channel_command, filters.command("add_channel") & private_commands))
        bot_client.add_handler(MessageHandler(self.remove_channel_command, filters.command("remove_channel") & private_commands))
        bot_client.add_handler(MessageHandler(self.list_channels_command, filters.command("list_channels") & private_commands))
