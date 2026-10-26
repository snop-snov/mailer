"""Parsing and building t.me message links. Pure functions, no I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t|telegram)\.me/(?P<path>[^?#\s]+)(?:\?(?P<query>[^#\s]*))?(?:#\S*)?$",
    re.IGNORECASE,
)
_USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")

# First path segments of t.me URLs that are not chat usernames.
_RESERVED = {"c", "s", "joinchat", "addstickers", "addemoji", "share", "proxy", "socks"}


@dataclass(frozen=True)
class MessageLink:
    # A -100… chat id for private chats (t.me/c/…), "@username" for public ones.
    chat: int | str
    message_id: int


def parse_message_link(text: str) -> MessageLink | None:
    """Parse a link to a message, or return None if `text` is not exactly one.

    Accepts t.me/c/<id>/<msg>, t.me/<username>/<msg> and the topic forms with an
    extra <topic> segment (the message id is always the last one). Links to
    channel comments (?comment=) point into another chat and are rejected.
    """
    match = _LINK_RE.match(text.strip())
    if match is None:
        return None
    query = match["query"] or ""
    if "comment=" in query:
        return None

    parts = match["path"].strip("/").split("/")
    if not all(part.isdigit() for part in parts[-1:]):
        return None
    message_id = int(parts[-1])
    if message_id <= 0:
        return None

    if parts[0].lower() == "c":
        # c/<id>/<msg> or c/<id>/<topic>/<msg>
        if len(parts) not in (3, 4) or not all(p.isdigit() for p in parts[1:]):
            return None
        return MessageLink(chat=int(f"-100{int(parts[1])}"), message_id=message_id)

    if parts[0].lower() in _RESERVED or not _USERNAME_RE.match(parts[0]):
        return None
    # <username>/<msg> or <username>/<topic>/<msg>
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts[1:]):
        return None
    return MessageLink(chat=f"@{parts[0]}", message_id=message_id)


def build_message_url(
    chat_id: int, username: str | None, message_id: int
) -> str | None:
    """A t.me link to a message, or None when the chat has no linkable form."""
    if username:
        return f"https://t.me/{username}/{message_id}"
    raw = str(chat_id)
    if raw.startswith("-100"):
        return f"https://t.me/c/{raw[4:]}/{message_id}"
    return None  # basic groups have no message links
