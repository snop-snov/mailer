"""Private-chat handlers: confirm with the sender, then copy to moderation."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, ForceReply, LinkPreviewOptions, Message
from aiogram.utils.formatting import Text, TextLink

from bot.config import Settings
from bot.keyboards import (
    CANCEL_CALLBACK,
    REPLY_CALLBACK,
    TAGS,
    build_moderation_keyboard,
    build_send_keyboard,
    build_tag_keyboard,
    unpack,
)
from bot.links import (
    MessageLink,
    build_ask_url,
    build_message_url,
    parse_ask_url,
    parse_message_link,
)
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
ASK_LINK_TEXT = " Пришлите ссылку на сообщение, на которое хотите ответить."
LINK_PLACEHOLDER = "https://t.me/…/123"
BAD_LINK_TEXT = (
    "Это не похоже на ссылку на сообщение. "
    "Пришлите только ссылку (https://t.me/…/123) ответом на моё сообщение выше."
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


def _link_request(message: Message) -> bool | dict[str, int | bool]:
    """Match a text sent as a reply to the "send a link" ask message.

    The ask message is recognised by the text link `build_ask_url` put on it,
    which also names the prompt to resume and whether it takes a tag.
    """
    ask = message.reply_to_message
    if not message.text or ask is None or not ask.entities:
        return False
    for entity in ask.entities:
        if entity.type == "text_link" and entity.url:
            parsed = parse_ask_url(entity.url)
            if parsed is not None:
                return {"prompt_id": parsed[0], "taggable": parsed[1]}
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
    message: Message, bot: Bot, settings: Settings, prompt_id: int, taggable: bool
) -> None:
    """The sender answered the "send a link" ask: validate it, then resume."""
    link = parse_message_link(message.text)
    if link is None:
        await message.reply(BAD_LINK_TEXT)
        return
    if not await _in_target_chat(bot, link, settings.target_chat_id):
        await message.reply(WRONG_CHAT_TEXT)
        return

    text, keyboard = _confirm_prompt(taggable, link.message_id)
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=prompt_id,
            text=f"{text}\n\n{REPLY_NOTE.format(url=message.text.strip())}",
            reply_markup=keyboard,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
    except Exception:
        logger.exception("Failed to show the chosen reply target")
        await message.reply(LOST_TEXT)
        return

    # The ask has served its purpose; drop it so it can't be answered twice.
    try:
        await message.reply_to_message.delete()
    except Exception:
        logger.warning("Could not delete the reply-link ask")


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
async def handle_reply_request(callback: CallbackQuery, bot: Bot) -> None:
    """Ask for a link with a ForceReply, so the client opens straight in reply mode."""
    prompt = callback.message
    original = prompt.reply_to_message if isinstance(prompt, Message) else None
    if original is None:
        await callback.answer(LOST_TEXT, show_alert=True)
        return

    url = build_ask_url(
        (await bot.me()).username,
        prompt.message_id,
        original.content_type in CAPTIONABLE,
    )
    try:
        # The leading arrow is the link carrying the payload; see build_ask_url.
        await prompt.answer(
            **Text(TextLink("↩️", url=url), ASK_LINK_TEXT).as_kwargs(),
            reply_markup=ForceReply(input_field_placeholder=LINK_PLACEHOLDER),
        )
    except Exception:
        logger.exception("Failed to ask for a reply link")
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
