from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    mongo_uri: str
    mongo_database: str = "telegram_automation"
    log_level: str = "INFO"
    bot_command_scope_private: bool = True
    default_send_delay: float = 0.5
    user_session_name: str = "userbot"
    bot_session_name: str = "bot"
    max_concurrent_sends: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        bot_token = os.getenv("BOT_TOKEN")
        mongo_uri = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI")

        missing = [
            name
            for name, value in {
                "API_ID": api_id,
                "API_HASH": api_hash,
                "BOT_TOKEN": bot_token,
                "MONGODB_URI/MONGO_URI": mongo_uri,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            api_id=int(api_id),
            api_hash=api_hash,
            bot_token=bot_token,
            mongo_uri=mongo_uri,
            mongo_database=os.getenv("MONGO_DATABASE", "telegram_automation"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            bot_command_scope_private=os.getenv("BOT_COMMAND_SCOPE_PRIVATE", "true").lower() == "true",
            default_send_delay=float(os.getenv("DEFAULT_SEND_DELAY", "0.5")),
            user_session_name=os.getenv("USER_SESSION_NAME", "userbot"),
            bot_session_name=os.getenv("BOT_SESSION_NAME", "bot"),
            max_concurrent_sends=int(os.getenv("MAX_CONCURRENT_SENDS", "5")),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
