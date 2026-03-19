from __future__ import annotations

import re
from dataclasses import dataclass

from pyrogram.types import MessageEntity

from utils.helpers import HASHTAG_PATTERN, URL_PATTERN, entity_copy


@dataclass(slots=True)
class EditedContent:
    text: str | None
    entities: list[MessageEntity] | None


class ContentEditor:
    @staticmethod
    def _replace_words(text: str, replace_words: dict[str, str]) -> str:
        for old, new in replace_words.items():
            text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
        return text

    def edit(
        self,
        text: str | None,
        entities: list[MessageEntity] | None,
        settings: dict,
    ) -> EditedContent:
        if not text:
            return EditedContent(text=None, entities=entities)

        prefix = settings.get("prefix", "")
        suffix = settings.get("suffix", "")
        replace_words = settings.get("replace_words", {})
        remove_links = settings.get("remove_links", False)
        remove_hashtags = settings.get("remove_hashtags", False)

        edited = text
        if replace_words:
            edited = self._replace_words(edited, replace_words)
        if remove_links:
            edited = URL_PATTERN.sub("", edited)
        if remove_hashtags:
            edited = HASHTAG_PATTERN.sub("", edited)

        edited = re.sub(r"\n{3,}", "\n\n", edited)
        edited = re.sub(r"[ \t]{2,}", " ", edited).strip()
        if prefix:
            edited = f"{prefix}{edited}"
        if suffix:
            edited = f"{edited}{suffix}"

        copied_entities = entity_copy(entities)
        if copied_entities and edited != text:
            # Pyrogram entity offsets are difficult to preserve after arbitrary edits.
            # We keep them only when surrounding with prefix/suffix is not changing content.
            if edited != f"{prefix}{text}{suffix}" or remove_links or remove_hashtags or replace_words:
                copied_entities = None

        return EditedContent(text=edited, entities=copied_entities)
