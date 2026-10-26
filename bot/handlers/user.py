"""Private-chat handlers: confirm with the sender, then copy to moderation."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, LinkPreviewOptions, Message

from bot.config import Settings
from bot.keyboards import (
    BACK_CALLBACK,
    CANCEL_CALLBACK,
    REPLY_CALLBACK,
    TAGS,
    build_link_request_keyboard,
    build_moderation_keyboard,
    build_send_keyboard,
    build_tag_keyboard,
    unpack,
)
from bot.links import MessageLink, build_message_url, parse_message_link
from bot.relay import CAPTIONABLE, relay

logger = logging.getLogger(__name__)

router = Router(name="user")
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

START_TEXT = (
    "Пришлите сообщение — текст, фото, видео, голосовое, документ или стикер — "
    "и я передам его анонимно."
)
CONFIRM_TAGGABLE_TEXT = (
    "Готово, отправляем в чат?\n"
    "Если фото ваше, можно выбрать тег #моё, если нет, тег #не_моё."
)
CONFIRM_PLAIN_TEXT = "Готово, отправляем в чат?"
SENT_TEXT = "✅ Отправлено!"
FAILED_TEXT = "⚠️ Не получилось отправить. Попробуйте ещё раз позже."
LOST_TEXT = "Не вижу исходное сообщение — пришлите его ещё раз."
CANCELLED_TEXT = (
    "❌ Сообщение не отправлено. Пришлите следующее собщение, чтобы продолжить."
)
# HTML: the bot sends plain text by default, this one message needs bold.
ASK_LINK_TEXT = (
    "Пришлите ссылку на сообщение, на которое хотите ответить \n"
    "<b>↩️ ответом на это сообщение</b>."
)
BAD_LINK_TEXT = (
    "Это не похоже на ссылку на сообщение. Пришлите только ссылку "
    "(https://t.me/…/123) ответом на моё сообщение выше."
)
WRONG_CHAT_TEXT = (
    "Эта ссылка ведёт в другой чат. Ответить можно только на сообщение в нашем чате."
)
REPLY_NOTE = "↩️ Ответ на: {url}"


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(START_TEXT)


def _confirm_prompt(taggable: bool, reply_to: int | None = None):
    if taggable:
        return CONFIRM_TAGGABLE_TEXT, build_tag_keyboard(reply_to)
    return CONFIRM_PLAIN_TEXT, build_send_keyboard(reply_to)


def _link_request(message: Message) -> bool | dict[str, bool]:
    """Match a text sent as a reply to the "send a link" prompt.

    That prompt is recognised by its Back button, which also says whether the
    submission can take a tag — the prompt itself no longer exposes the
    submission it replies to.
    """
    prompt = message.reply_to_message
    if not message.text or prompt is None or prompt.reply_markup is None:
        return False
    for row in prompt.reply_markup.inline_keyboard:
        for button in row:
            data = button.callback_data or ""
            if data.startswith(f"{BACK_CALLBACK}:"):
                return {"taggable": data.endswith(":t")}
    return False


async def _in_target_chat(bot: Bot, link: MessageLink, target_chat_id: int) -> bool:
    if isinstance(link.chat, int):
        return link.chat == target_chat_id
    try:
        chat = await bot.get_chat(link.chat)
    except TelegramAPIError:
        return False
    return chat.id == target_chat_id


async def _reply_url(bot: Bot, chat_id: int, message_id: int | None) -> str | None:
    if message_id is None:
        return None
    username = None
    try:
        username = (await bot.get_chat(chat_id)).username
    except TelegramAPIError:
        logger.warning("Could not look up the target chat's username")
    return build_message_url(chat_id, username, message_id)


@router.message(F.text, _link_request)
async def handle_link(
    message: Message, bot: Bot, settings: Settings, taggable: bool
) -> None:
    """The sender answered the "send a link" prompt: validate it, then resume."""
    prompt = message.reply_to_message
    link = parse_message_link(message.text)
    if link is None:
        await message.reply(BAD_LINK_TEXT)
        return
    if not await _in_target_chat(bot, link, settings.target_chat_id):
        await message.reply(WRONG_CHAT_TEXT)
        return

    text, keyboard = _confirm_prompt(taggable, link.message_id)
    try:
        await prompt.edit_text(
            f"{text}\n\n{REPLY_NOTE.format(url=message.text.strip())}",
            reply_markup=keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        logger.exception("Failed to show the chosen reply target")


@router.message()
async def handle_submission(message: Message) -> None:
    text, keyboard = _confirm_prompt(message.content_type in CAPTIONABLE)

    # Replying links the prompt to the submission, so the callback can recover
    # the original message without us storing anything.
    await message.reply(text, reply_markup=keyboard)


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


@router.callback_query(F.data == REPLY_CALLBACK)
async def handle_reply_request(callback: CallbackQuery) -> None:
    """Ask for a link; the prompt becomes the thing the link is sent in reply to."""
    prompt = callback.message
    original = prompt.reply_to_message if isinstance(prompt, Message) else None
    if original is None:
        await callback.answer(LOST_TEXT, show_alert=True)
        return
    try:
        await prompt.edit_text(
            ASK_LINK_TEXT,
            parse_mode="HTML",
            reply_markup=build_link_request_keyboard(
                original.content_type in CAPTIONABLE
            ),
        )
    except Exception:
        logger.exception("Failed to ask for a reply link")
    await callback.answer()


@router.callback_query(F.data.startswith(f"{BACK_CALLBACK}:"))
async def handle_back(callback: CallbackQuery) -> None:
    """Abandon the reply and go back to the plain confirm prompt."""
    prompt = callback.message
    if isinstance(prompt, Message):
        text, keyboard = _confirm_prompt(callback.data.endswith(":t"))
        try:
            await prompt.edit_text(text, reply_markup=keyboard)
        except Exception:
            logger.exception("Failed to restore the confirm prompt")
    await callback.answer()


@router.callback_query(F.data.func(lambda data: unpack(data)[0] in TAGS))
async def handle_tag_choice(
    callback: CallbackQuery, bot: Bot, settings: Settings
) -> None:
    prompt = callback.message
    original = prompt.reply_to_message if isinstance(prompt, Message) else None
    if original is None:
        await callback.answer(LOST_TEXT, show_alert=True)
        return

    tag_key, reply_to = unpack(callback.data)

    # Drop the buttons first so a double tap cannot submit twice.
    try:
        await prompt.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception("Failed to clear the tag keyboard")

    try:
        await relay(
            bot,
            settings.moderation_chat_id,
            original,
            tag=TAGS[tag_key],
            reply_markup=build_moderation_keyboard(
                reply_to, await _reply_url(bot, settings.target_chat_id, reply_to)
            ),
        )
    except Exception:
        # Never log message content or sender identity — only that it failed.
        logger.exception("Failed to copy a submission to the moderation chat")
        await prompt.edit_text(FAILED_TEXT)
        await callback.answer()
        return

    await prompt.edit_text(SENT_TEXT)
    await callback.answer()
