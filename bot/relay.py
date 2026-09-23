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


async def relay(
    bot: Bot,
    chat_id: int,
    message: Message,
    *,
    tag: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Copy `message` into `chat_id` with no sender attribution.

    `tag`, when given, is appended on a new line to the caption (or the text,
    for a text message). Never spoilers media — this is used to deliver
    submissions into the moderation chat, where moderators need to see the
    actual content to judge it.
    """
    content_type = message.content_type

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


async def publish(
    bot: Bot,
    chat_id: int,
    message: Message,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Deliver an already-anonymized moderation-chat `message` into `chat_id`.

    Coverable media is spoilered; copy_message has no has_spoiler parameter,
    so it's resent by file_id instead. The file_id comes from the moderation
    chat's own copy, not the original submitter's chat, so this doesn't
    reintroduce any attribution. Any tag is already baked into the caption
    from when the message was copied into moderation.
    """
    if message.content_type in SPOILERABLE:
        common = {
            "chat_id": chat_id,
            "caption": message.caption,
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
        return

    await bot.copy_message(
        chat_id=chat_id,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=reply_markup,
    )
