from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment variables.

    Telegram API credentials are available from https://my.telegram.org after signing in.
    Generate SESSION_STRING locally with generate_session.py, then store it in your
    Render service environment variables so the deployed user client never prompts for OTP.
    """

    api_id: int
    api_hash: str
    bot_token: str
    session_string: str
    mongo_uri: str
    mongo_database: str = "telegram_automation"
    log_level: str = "INFO"
    default_send_delay: float = 0.5
    user_session_name: str = "user_session"
    bot_session_name: str = "bot_session"
    max_concurrent_sends: int = 5

    @classmethod
    def from_env(cls) -> "Settings":
        # Get API_ID and API_HASH from https://my.telegram.org.
        api_id = os.getenv("API_ID")
        api_hash = os.getenv("API_HASH")
        bot_token = os.getenv("BOT_TOKEN")
        # SESSION_STRING should be generated locally once and saved in Render env vars.
        session_string = os.getenv("SESSION_STRING")
        mongo_uri = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")

        missing = [
            name
            for name, value in {
                "API_ID": api_id,
                "API_HASH": api_hash,
                "BOT_TOKEN": bot_token,
                "SESSION_STRING": session_string,
                "MONGO_URI/MONGODB_URI": mongo_uri,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            api_id=int(api_id),
            api_hash=api_hash,
            bot_token=bot_token,
            session_string=session_string,
            mongo_uri=mongo_uri,
            mongo_database=os.getenv("MONGO_DATABASE", "telegram_automation"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            default_send_delay=float(os.getenv("DEFAULT_SEND_DELAY", "0.5")),
            user_session_name=os.getenv("USER_SESSION_NAME", "user_session"),
            bot_session_name=os.getenv("BOT_SESSION_NAME", "bot_session"),
            max_concurrent_sends=int(os.getenv("MAX_CONCURRENT_SENDS", "5")),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
