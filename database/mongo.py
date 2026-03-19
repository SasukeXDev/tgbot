from __future__ import annotations

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from config import Settings

logger = logging.getLogger(__name__)


CHANNEL_INDEX_FIELDS = [("source_channel", 1)]


class MongoRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncIOMotorClient(settings.mongo_uri)
        self._db: AsyncIOMotorDatabase = self._client[settings.mongo_database]
        self.channels: AsyncIOMotorCollection = self._db["channels"]

    async def connect(self) -> None:
        await self._db.command("ping")
        await self.channels.create_index(CHANNEL_INDEX_FIELDS, unique=True)
        logger.info("Connected to MongoDB database '%s'", self._settings.mongo_database)

    async def close(self) -> None:
        self._client.close()
        logger.info("MongoDB connection closed")

    async def get_all_channels(self) -> list[dict[str, Any]]:
        return await self.channels.find().to_list(length=None)

    async def add_channel(self, payload: dict[str, Any]) -> None:
        await self.channels.update_one(
            {"source_channel": payload["source_channel"]},
            {"$set": payload},
            upsert=True,
        )

    async def remove_channel(self, source_channel: str) -> int:
        result = await self.channels.delete_one({"source_channel": source_channel})
        return result.deleted_count
