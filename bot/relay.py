"""Shared delivery logic for moving a message between chats anonymously.

Nothing here keeps state between updates: every call works purely from the
`Message` object in the current update.
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message

# Telegram only supports a spoiler overlay on these. Documents, audio and voice
# cannot be covered, so a photo sent as an uncompressed file stays visible.
SPOILERABLE = {"photo", "video", "animation"}

# Content types Telegram lets us attach a caption to.
CAPTIONABLE = {"photo", "video", "animation", "audio", "document", "voice"}


async def _send_spoilered(
    bot: Bot,
    chat_id: int,
    message: Message,
    caption: str | None,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    """Re-send media by file_id so a spoiler can be applied.

    copy_message has no has_spoiler parameter, so copying is not an option when
    the media needs covering.
    """
    common = {
        "chat_id": chat_id,
        "caption": caption,
        "caption_entities": message.caption_entities,
        "has_spoiler": True,
        "reply_markup": reply_markup,
    }
    if message.photo:
        await bot.send_photo(photo=message.photo[-1].file_id, **common)
    elif message.video:
        await bot.send_video(video=message.video.file_id, **common)
    else:
        await bot.send_animation(animation=message.animation.file_id, **common)


async def relay(
    bot: Bot,
    chat_id: int,
    message: Message,
    *,
    tag: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Deliver `message` into `chat_id` with no sender attribution.

    Media is covered by a spoiler. `tag`, when given, is appended on a new line
    to the caption (or the text, for a text message).
    """
    content_type = message.content_type

    if content_type in SPOILERABLE:
        caption = message.caption
        if tag:
            caption = f"{caption}\n{tag}" if caption else tag
        await _send_spoilered(bot, chat_id, message, caption, reply_markup)
        return

    if message.text is not None:
        if tag:
            # copy_message cannot rewrite text, so resend it. Existing entities
            # stay valid because the tag is appended at the end.
            await bot.send_message(
                chat_id=chat_id,
                text=f"{message.text}\n{tag}",
                entities=message.entities,
                reply_markup=reply_markup,
            )
            return
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=reply_markup,
        )
        return

    if tag and content_type in CAPTIONABLE:
        caption = f"{message.caption}\n{tag}" if message.caption else tag
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            caption_entities=message.caption_entities,
            reply_markup=reply_markup,
        )
        return

    # Stickers, video notes and friends: copy as-is. copy_message strips any
    # "forwarded from" attribution.
    await bot.copy_message(
        chat_id=chat_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=reply_markup,
    )
