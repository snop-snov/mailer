"""Moderation-chat handlers: approve forwards the copy on, reject drops it."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from bot.config import Settings
from bot.keyboards import (
    APPROVE_CALLBACK,
    DONE_CALLBACK,
    REJECT_CALLBACK,
    build_status_keyboard,
)
from bot.relay import relay

logger = logging.getLogger(__name__)

router = Router(name="moderation")


@router.callback_query(F.data == DONE_CALLBACK)
async def handle_done(callback: CallbackQuery) -> None:
    """The status button is inert — just dismiss the spinner."""
    await callback.answer()


@router.callback_query(F.data.in_({APPROVE_CALLBACK, REJECT_CALLBACK}))
async def handle_moderation(
    callback: CallbackQuery, bot: Bot, settings: Settings
) -> None:
    message = callback.message
    # Only act on buttons that live in the configured moderation chat.
    if message is None or message.chat.id != settings.moderation_chat_id:
        await callback.answer("Not available here.", show_alert=True)
        return

    who = callback.from_user.full_name

    if callback.data == APPROVE_CALLBACK:
        try:
            # Relay rather than copy: copy_message cannot set has_spoiler, so a
            # plain copy would publish the media uncovered.
            await relay(bot, settings.target_chat_id, message)
        except Exception:
            logger.exception("Failed to copy an approved message to the target chat")
            await callback.answer("Publishing failed, try again.", show_alert=True)
            return
        status, toast = f"✅ Approved by {who}", "Published ✅"
    else:
        status, toast = f"❌ Rejected by {who}", "Rejected ❌"

    # Replace the buttons with the outcome so the decision stays visible in chat.
    try:
        await bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=build_status_keyboard(status),
        )
    except Exception:
        logger.exception("Failed to mark the moderated message")

    await callback.answer(toast)
