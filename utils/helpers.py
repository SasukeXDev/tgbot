from __future__ import annotations

import copy
import logging
import re
from collections.abc import Iterable
from typing import Any

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#\w+")


def normalize_channel_key(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip().lower()
    return str(value)


def collect_channel_keys(chat_id: int | None, username: str | None) -> set[str]:
    keys = set()
    if chat_id is not None:
        keys.add(str(chat_id))
    if username:
        keys.add(username.lower())
        keys.add(f"@{username.lower().lstrip('@')}")
    return keys


def build_reply_markup(buttons: Iterable[dict[str, str]] | None) -> InlineKeyboardMarkup | None:
    rows: list[list[InlineKeyboardButton]] = []
    if not buttons:
        return None

    current_row: list[InlineKeyboardButton] = []
    for button in buttons:
        text = button.get("text")
        url = button.get("url")
        if not text or not url:
            logger.warning("Skipping invalid button config: %s", button)
            continue
        current_row.append(InlineKeyboardButton(text=text, url=url))
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(rows) if rows else None


def entity_copy(entities: list[MessageEntity] | None) -> list[MessageEntity] | None:
    return [copy.deepcopy(entity) for entity in entities] if entities else None
