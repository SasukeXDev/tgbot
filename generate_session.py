from __future__ import annotations

import asyncio

from pyrogram import Client

from config import get_settings


async def main() -> None:
    settings = get_settings()

    # Get API_ID and API_HASH from https://my.telegram.org and run this file locally.
    # After login, copy the printed SESSION_STRING into your Render environment variables.
    async with Client(
        "session_generator",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        in_memory=True,
    ) as app:
        session_string = await app.export_session_string()
        print("\nSESSION_STRING=\n")
        print(session_string)
        print("\nSave this value in Render as SESSION_STRING before deployment.\n")


if __name__ == "__main__":
    asyncio.run(main())
