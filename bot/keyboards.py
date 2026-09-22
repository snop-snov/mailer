"""Inline keyboards. Callback payloads are static: no per-message state is kept."""

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

CANCEL_TEXT = "❌ Стоп Отмена!!"

TAGS: dict[str, str | None] = {
    NO_TAG_CALLBACK: None,
    MINE_CALLBACK: "#моё",
    NOT_MINE_CALLBACK: "#не_моё",
}


def build_moderation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=APPROVE_CALLBACK)
    builder.button(text="❌ Reject", callback_data=REJECT_CALLBACK)
    builder.adjust(2)
    return builder.as_markup()


def build_tag_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="без тега", callback_data=NO_TAG_CALLBACK)
    builder.button(text="#моё", callback_data=MINE_CALLBACK)
    builder.button(text="#не_моё", callback_data=NOT_MINE_CALLBACK)
    builder.button(text=CANCEL_TEXT, callback_data=CANCEL_CALLBACK)
    builder.adjust(3, 1)
    return builder.as_markup()


def build_send_keyboard() -> InlineKeyboardMarkup:
    """For content Telegram cannot attach a caption to — no tag choice to make."""
    builder = InlineKeyboardBuilder()
    builder.button(text="отправляем!", callback_data=NO_TAG_CALLBACK)
    builder.button(text=CANCEL_TEXT, callback_data=CANCEL_CALLBACK)
    builder.adjust(1, 1)
    return builder.as_markup()


def build_status_keyboard(text: str) -> InlineKeyboardMarkup:
    """A single inert button that records the decision on the message itself."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text[:64], callback_data=DONE_CALLBACK)
    return builder.as_markup()
