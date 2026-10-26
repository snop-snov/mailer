"""Inline keyboards.

No per-message state is kept server-side. The only dynamic payload is the id of
the target-chat message a submission replies to, appended to the callback data
as ``<base>:<message_id>`` so it travels with the buttons themselves.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

APPROVE_CALLBACK = "mod:approve"
REJECT_CALLBACK = "mod:reject"
DONE_CALLBACK = "mod:done"

# Tag choices offered to the sender before anything reaches moderation.
# The chosen tag is the whole payload, so no per-message state is needed.
NO_TAG_CALLBACK = "snd:none"
MINE_CALLBACK = "snd:mine"
NOT_MINE_CALLBACK = "snd:notmine"
CANCEL_CALLBACK = "snd:cancel"
REPLY_CALLBACK = "snd:reply"

CANCEL_TEXT = "❌ Стоп Отмена!!"
REPLY_TEXT = "↩️ Ответить на сообщение"
REPLY_CHANGE_TEXT = "↩️ Другое сообщение"
REPLY_URL_TEXT = "↩️ Replying to message"

TAGS: dict[str, str | None] = {
    NO_TAG_CALLBACK: None,
    MINE_CALLBACK: "#моё",
    NOT_MINE_CALLBACK: "#не_моё",
}


def pack(base: str, reply_to: int | None = None) -> str:
    """Append the id of the message to reply to, if any, to a callback payload."""
    return f"{base}:{reply_to}" if reply_to else base


def unpack(data: str | None) -> tuple[str, int | None]:
    """Inverse of `pack`. Payloads without an id (older prompts) give None."""
    data = data or ""
    head, sep, tail = data.rpartition(":")
    if sep and tail.isdigit():
        return head, int(tail)
    return data, None


def _reply_url_button(builder: InlineKeyboardBuilder, reply_url: str | None) -> bool:
    if reply_url:
        builder.button(text=REPLY_URL_TEXT, url=reply_url)
        return True
    return False


def build_moderation_keyboard(
    reply_to: int | None = None, reply_url: str | None = None
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=pack(APPROVE_CALLBACK, reply_to))
    builder.button(text="❌ Reject", callback_data=pack(REJECT_CALLBACK, reply_to))
    rows = [2]
    if _reply_url_button(builder, reply_url):
        rows.append(1)
    builder.adjust(*rows)
    return builder.as_markup()


def build_tag_keyboard(reply_to: int | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="без тега", callback_data=pack(NO_TAG_CALLBACK, reply_to))
    builder.button(text="#моё", callback_data=pack(MINE_CALLBACK, reply_to))
    builder.button(text="#не_моё", callback_data=pack(NOT_MINE_CALLBACK, reply_to))
    builder.button(
        text=REPLY_CHANGE_TEXT if reply_to else REPLY_TEXT,
        callback_data=REPLY_CALLBACK,
    )
    builder.button(text=CANCEL_TEXT, callback_data=CANCEL_CALLBACK)
    builder.adjust(3, 1, 1)
    return builder.as_markup()


def build_send_keyboard(reply_to: int | None = None) -> InlineKeyboardMarkup:
    """For content Telegram cannot attach a caption to — no tag choice to make."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправляем!", callback_data=pack(NO_TAG_CALLBACK, reply_to))
    builder.button(
        text=REPLY_CHANGE_TEXT if reply_to else REPLY_TEXT,
        callback_data=REPLY_CALLBACK,
    )
    builder.button(text=CANCEL_TEXT, callback_data=CANCEL_CALLBACK)
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def build_status_keyboard(
    text: str, reply_url: str | None = None
) -> InlineKeyboardMarkup:
    """A single inert button that records the decision on the message itself."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text[:64], callback_data=DONE_CALLBACK)
    rows = [1]
    if _reply_url_button(builder, reply_url):
        rows.append(1)
    builder.adjust(*rows)
    return builder.as_markup()
