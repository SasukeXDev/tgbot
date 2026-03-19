# Telegram Automation System

Production-ready Telegram automation system built with Python, Pyrogram, asyncio, and MongoDB. A user account listens to source channels, processes incoming content, and a bot account republishes the modified content to destination channels without forwarding tags.

## Render Deployment Fixes

This project is configured for Render with:

- `runtime.txt` pinned to `python-3.11.9` because Pyrogram `2.0.106` does not support Python `3.14` yet.
- A fully async `main.py` that uses `asyncio.run(...)` and avoids `pyrogram.idle()`.
- `SESSION_STRING` support so the user client does not request OTP during deployment.
- Startup channel validation so inaccessible peers are logged and skipped instead of crashing the worker.

## Features

- Dual Pyrogram clients: user account for reading, bot account for publishing.
- MongoDB-backed channel routing and edit rules.
- Message processing for text, photos, videos, and documents.
- Inline button support.
- Configurable delay and concurrency controls to reduce spam-limit issues.
- Admin bot commands for adding, removing, and listing routes.
- Ready for deployment on Render, Koyeb, VPS, or similar platforms.

## Project Structure

```text
project/
├── main.py
├── config.py
├── generate_session.py
├── runtime.txt
├── database/
│   └── mongo.py
├── handlers/
│   └── message_handler.py
├── services/
│   ├── editor.py
│   └── sender.py
├── utils/
│   └── helpers.py
├── requirements.txt
└── .env.example
```

## Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

- `API_ID`: Telegram API ID from https://my.telegram.org.
- `API_HASH`: Telegram API hash from https://my.telegram.org.
- `BOT_TOKEN`: Telegram bot token from BotFather.
- `SESSION_STRING`: Generate locally with `python generate_session.py`, then paste it into Render environment variables.
- `MONGO_URI`: MongoDB connection string.
- `MONGO_DATABASE`: Database name, defaults to `telegram_automation`.
- `DEFAULT_SEND_DELAY`: Fallback delay between sends.
- `MAX_CONCURRENT_SENDS`: Limit concurrent outgoing bot sends.

## Generate the User Session String

Run this locally on your computer or development machine, not on Render:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python generate_session.py
```

Important sequence:

1. Log in locally with the same Telegram account.
2. Join every source channel manually first.
3. Generate the session string.
4. Save it in Render as `SESSION_STRING`.
5. Deploy the worker.

This prevents `Peer id invalid` errors caused by a session that has never accessed the source channel.

## MongoDB Channel Schema

Create documents inside the `channels` collection like this:

```json
{
  "source_channel": "@source_username_or_id",
  "destination_channel": "@destination_username_or_id",
  "source_invite_link": "https://t.me/+optionalInviteHash",
  "edit_settings": {
    "prefix": "[Edited] ",
    "suffix": "\n\nJoin our network!",
    "replace_words": {
      "old": "new"
    },
    "remove_links": true,
    "remove_hashtags": false
  },
  "buttons": [
    {
      "text": "Join Now",
      "url": "https://t.me/yourchannel"
    }
  ],
  "delay": 1.0
}
```

Notes:

- Prefer `@channel_username` over raw numeric ids like `-100...` for more reliable peer resolution.
- If a source is private, you can optionally store `source_invite_link` so startup can try `join_chat(...)` once.
- Inaccessible channels are skipped and logged instead of crashing the process.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Admin Commands

Send these commands to the bot in a private chat:

- `/add_channel <source> <destination> [prefix]`
- `/remove_channel <source>`
- `/list_channels`

## Deploy on Render

1. Create a **Background Worker** on Render.
2. Do **not** use a Web Service for this project because it does not expose HTTP and does not need a port.
3. Make sure Render uses `python-3.11.9` from `runtime.txt`.
4. Add these environment variables in Render: `API_ID`, `API_HASH`, `BOT_TOKEN`, `SESSION_STRING`, `MONGO_URI`, and optional tuning values.
5. Deploy with the start command:

```bash
python main.py
```

## Deployment Notes

- Make sure both the user account and the bot are members/admins of their required channels.
- For private source channels, the user session must already have access, or you must provide a usable `source_invite_link`.
- Because Render is non-interactive, never rely on OTP login there; always use `SESSION_STRING`.
- On startup, the worker validates source-channel access and logs `Access OK`, `Cannot access`, and `Skipping inaccessible source channel` messages for debugging.
- Use Render worker auto-restart or another process manager for resilience.
