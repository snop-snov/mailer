"""Private-chat handlers: take whatever the user sends and copy it to moderation."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.config import Settings
from bot.keyboards import build_moderation_keyboard

logger = logging.getLogger(__name__)

router = Router(name="user")
router.message.filter(F.chat.type == "private")

START_TEXT = (
    "Send me a message — text, photo, video, voice, document or sticker — "
    "and I'll pass it on anonymously."
)
SENT_TEXT = "✅ Sent."
FAILED_TEXT = "⚠️ Couldn't send your message. Please try again later."


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT)


@router.message()
async def handle_submission(message: Message, bot: Bot, settings: Settings) -> None:
    try:
        # copy_message strips any "forwarded from" attribution, so the copy in the
        # moderation chat carries no link back to the sender.
        await bot.copy_message(
            chat_id=settings.moderation_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=build_moderation_keyboard(),
        )
    except Exception:
        # Never log message content or sender identity — only that a copy failed.
        logger.exception("Failed to copy a submission to the moderation chat")
        await message.answer(FAILED_TEXT)
        return

    await message.answer(SENT_TEXT)
