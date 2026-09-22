"""Inline keyboards. Callback payloads are static: no per-message state is kept."""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

APPROVE_CALLBACK = "mod:approve"
REJECT_CALLBACK = "mod:reject"
DONE_CALLBACK = "mod:done"


def build_moderation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Approve", callback_data=APPROVE_CALLBACK)
    builder.button(text="❌ Reject", callback_data=REJECT_CALLBACK)
    builder.adjust(2)
    return builder.as_markup()


def build_status_keyboard(text: str) -> InlineKeyboardMarkup:
    """A single inert button that records the decision on the message itself."""
    builder = InlineKeyboardBuilder()
    builder.button(text=text[:64], callback_data=DONE_CALLBACK)
    return builder.as_markup()
