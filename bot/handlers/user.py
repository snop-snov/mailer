"""Private-chat handlers: confirm with the sender, then copy to moderation."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.config import Settings
from bot.keyboards import (
    CANCEL_CALLBACK,
    TAGS,
    build_moderation_keyboard,
    build_send_keyboard,
    build_tag_keyboard,
)

logger = logging.getLogger(__name__)

router = Router(name="user")
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

START_TEXT = (
    "Пришлите сообщение — текст, фото, видео, голосовое, документ или стикер — "
    "и я передам его анонимно."
)
CONFIRM_TAGGABLE_TEXT = (
    "Готово, отправляем в чат? Если фото ваше, можно выбрать тег #моё, "
    "если нет, тег #не_моё."
)
CONFIRM_PLAIN_TEXT = "Готово, отправляем в чат?"
SENT_TEXT = "Отправлено ✅"
FAILED_TEXT = "⚠️ Не получилось отправить. Попробуйте ещё раз позже."
LOST_TEXT = "Не вижу исходное сообщение — пришлите его ещё раз."
CANCELLED_TEXT = (
    "Сообщение не отправлено. Пришли следующее собщение, чтобы продолжить."
)

# Content types Telegram lets us attach a caption to. Only these get offered a
# tag; everything else (text, stickers, video notes) just gets a send button.
CAPTIONABLE = {"photo", "video", "animation", "audio", "document", "voice"}


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message()
async def handle_submission(message: Message) -> None:
    if message.content_type in CAPTIONABLE:
        text, keyboard = CONFIRM_TAGGABLE_TEXT, build_tag_keyboard()
    else:
        text, keyboard = CONFIRM_PLAIN_TEXT, build_send_keyboard()

    # Replying links the prompt to the submission, so the callback can recover
    # the original message without us storing anything.
    await message.reply(text, reply_markup=keyboard)


async def _deliver(bot: Bot, settings: Settings, message: Message, tag: str | None) -> None:
    """Put the submission into the moderation chat, with the tag on a new line."""
    keyboard = build_moderation_keyboard()

    if tag is None:
        # copy_message strips any "forwarded from" attribution.
        await bot.copy_message(
            chat_id=settings.moderation_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=keyboard,
        )
        return

    if message.text is not None:
        # Text is no longer offered a tag, but a prompt created before that
        # change can still be tapped, so keep handling it. copy_message cannot
        # rewrite text, so resend it instead; existing entities stay valid
        # because the tag is appended at the end.
        await bot.send_message(
            chat_id=settings.moderation_chat_id,
            text=f"{message.text}\n{tag}",
            entities=message.entities,
            reply_markup=keyboard,
        )
        return

    if message.content_type in CAPTIONABLE:
        caption = f"{message.caption}\n{tag}" if message.caption else tag
        await bot.copy_message(
            chat_id=settings.moderation_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            caption_entities=message.caption_entities,
            reply_markup=keyboard,
        )
        return

    # Stickers, video notes and friends carry no caption — send them untagged.
    await bot.copy_message(
        chat_id=settings.moderation_chat_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=keyboard,
    )


@router.callback_query(F.data == CANCEL_CALLBACK)
async def handle_cancel(callback: CallbackQuery) -> None:
    """Drop the submission; nothing is forwarded."""
    prompt = callback.message
    if isinstance(prompt, Message):
        try:
            await prompt.edit_text(CANCELLED_TEXT)
        except Exception:
            logger.exception("Failed to mark the prompt as cancelled")
    await callback.answer()


@router.callback_query(F.data.in_(TAGS))
async def handle_tag_choice(
    callback: CallbackQuery, bot: Bot, settings: Settings
) -> None:
    prompt = callback.message
    original = prompt.reply_to_message if isinstance(prompt, Message) else None
    if original is None:
        await callback.answer(LOST_TEXT, show_alert=True)
        return

    # Drop the buttons first so a double tap cannot submit twice.
    try:
        await prompt.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Failed to clear the tag keyboard")

    try:
        await _deliver(bot, settings, original, TAGS[callback.data])
    except Exception:
        # Never log message content or sender identity — only that it failed.
        logger.exception("Failed to copy a submission to the moderation chat")
        await prompt.edit_text(FAILED_TEXT)
        await callback.answer()
        return

    await prompt.edit_text(SENT_TEXT)
    await callback.answer()
