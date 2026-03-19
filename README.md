# Telegram Automation System

Production-ready Telegram automation system built with Python, Pyrogram, asyncio, and MongoDB. A user account listens to source channels, processes incoming content, and a bot account republishes the modified content to destination channels without forwarding tags.

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

- `API_ID`: Telegram API ID for the user account.
- `API_HASH`: Telegram API hash for the user account.
- `BOT_TOKEN`: Telegram bot token from BotFather.
- `MONGODB_URI`: MongoDB connection string.
- `MONGO_DATABASE`: Database name, defaults to `telegram_automation`.
- `DEFAULT_SEND_DELAY`: Fallback delay between sends.
- `MAX_CONCURRENT_SENDS`: Limit concurrent outgoing bot sends.

## MongoDB Channel Schema

Create documents inside the `channels` collection like this:

```json
{
  "source_channel": "@source_username_or_id",
  "destination_channel": "@destination_username_or_id",
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

## Deployment Notes

- Make sure both the user account and the bot are members/admins of their required channels.
- For private source channels, the user session must already have access.
- The first run will prompt for the user account login/session creation.
- Use process managers such as systemd, Supervisor, or your cloud provider's worker service for production.
