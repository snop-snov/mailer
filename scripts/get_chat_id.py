"""Print the chat id of every chat the bot receives an update from.

Usage:  python scripts/get_chat_id.py   (Ctrl-C to stop)

Add the bot to the chat, then post any message there (or, for a channel, make
the bot an admin and post). The chat id shows up here. Nothing is stored.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.parse
import urllib.request

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import json

TOKEN = os.environ.get("BOT_TOKEN", "").strip()
if not TOKEN:
    sys.exit("BOT_TOKEN is not set (put it in .env)")

API = f"https://api.telegram.org/bot{TOKEN}"
KEYS = (
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "my_chat_member",
    "callback_query",
)


def get_updates(offset: int | None) -> list[dict]:
    params = {"timeout": "30"}
    if offset is not None:
        params["offset"] = str(offset)
    url = f"{API}/getUpdates?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=40) as resp:
        payload = json.load(resp)
    if not payload.get("ok"):
        sys.exit(f"Telegram error: {payload}")
    return payload["result"]


def main() -> None:
    print("Waiting for updates — send a message in the chat. Ctrl-C to stop.\n")
    offset: int | None = None
    seen: set[int] = set()
    while True:
        try:
            updates = get_updates(offset)
        except KeyboardInterrupt:
            return
        except Exception as exc:  # network hiccup: back off and retry
            print(f"retrying after error: {exc}")
            time.sleep(3)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            for key in KEYS:
                event = update.get(key)
                if not event:
                    continue
                chat = event.get("chat") or (event.get("message") or {}).get("chat")
                if not chat or chat["id"] in seen:
                    continue
                seen.add(chat["id"])
                title = (
                    chat.get("title")
                    or chat.get("username")
                    or chat.get("first_name")
                    or ""
                )
                print(f"{chat['id']}\t{chat['type']}\t{title}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
