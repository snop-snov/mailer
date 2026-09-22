"""Entrypoint: webhook server by default, long polling with ``--polling`` for dev."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.config import Settings, load_settings
from bot.handlers import moderation, user

logger = logging.getLogger(__name__)


def build_dispatcher(settings: Settings) -> Dispatcher:
    dp = Dispatcher()
    # Handlers receive `settings` as a keyword argument from the workflow data.
    dp["settings"] = settings
    dp.include_router(moderation.router)
    dp.include_router(user.router)
    return dp


def build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


def run_webhook(settings: Settings) -> None:
    bot = build_bot(settings)
    dp = build_dispatcher(settings)

    async def on_startup(_: web.Application) -> None:
        await bot.set_webhook(
            url=settings.webhook_url,
            secret_token=settings.webhook_secret_token,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
        )
        logger.info("Webhook set to %s", settings.webhook_url)

    async def on_shutdown(_: web.Application) -> None:
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Webhook deleted")

    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret_token,
    ).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=settings.web_server_host, port=settings.web_server_port)


def run_polling(settings: Settings) -> None:
    """Local development fallback — no public HTTPS endpoint required."""

    async def _main() -> None:
        bot = build_bot(settings)
        dp = build_dispatcher(settings)
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot)
        finally:
            await bot.session.close()

    asyncio.run(_main())


def main() -> None:
    try:  # optional convenience for local runs
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    polling = "--polling" in sys.argv[1:]
    settings = load_settings(require_webhook=not polling)
    if polling:
        run_polling(settings)
    else:
        run_webhook(settings)


if __name__ == "__main__":
    main()
