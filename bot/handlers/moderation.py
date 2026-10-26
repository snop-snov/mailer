"""Moderation-chat handlers: approve forwards the copy on, reject drops it."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.keyboards import (
    APPROVE_CALLBACK,
    DONE_CALLBACK,
    REJECT_CALLBACK,
    build_status_keyboard,
    unpack,
)
from bot.relay import publish

logger = logging.getLogger(__name__)

router = Router(name="moderation")


def _is_moderation_action(data: str | None) -> bool:
    return unpack(data)[0] in {APPROVE_CALLBACK, REJECT_CALLBACK}


def _reply_url(message: Message) -> str | None:
    """The link button to the replied-to message, if the submission has one."""
    if message.reply_markup is None:
        return None
    for row in message.reply_markup.inline_keyboard:
        for button in row:
            if button.url:
                return button.url
    return None


@router.callback_query(F.data == DONE_CALLBACK)
async def handle_done(callback: CallbackQuery) -> None:
    """The status button is inert — just dismiss the spinner."""
    await callback.answer()


@router.callback_query(F.data.func(_is_moderation_action))
async def handle_moderation(
    callback: CallbackQuery, bot: Bot, settings: Settings
) -> None:
    message = callback.message
    # Only act on buttons that live in the configured moderation chat.
    if message is None or message.chat.id != settings.moderation_chat_id:
        await callback.answer("Not available here.", show_alert=True)
        return

    who = callback.from_user.full_name
    action, reply_to = unpack(callback.data)

    if action == APPROVE_CALLBACK:
        try:
            # publish(), not copy_message directly: copy_message cannot set
            # has_spoiler, so a plain copy would leave the media uncovered.
            await publish(
                bot,
                settings.target_chat_id,
                message,
                reply_to_message_id=reply_to,
            )
        except Exception:
            logger.exception("Failed to publish an approved message to the target chat")
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
            reply_markup=build_status_keyboard(status, _reply_url(message)),
        )
    except Exception:
        logger.exception("Failed to mark the moderated message")

    await callback.answer(toast)
