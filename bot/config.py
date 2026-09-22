"""Environment-based settings. No secrets or message data are ever persisted."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when the environment is missing or has malformed settings."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Required environment variable {name} is not set")
    return value


def _require_int(name: str) -> int:
    raw = _require(name)
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str
    moderation_chat_id: int
    target_chat_id: int
    webhook_host: str
    webhook_path: str
    webhook_secret_token: str
    web_server_host: str
    web_server_port: int

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host.rstrip('/')}{self.webhook_path}"


def load_settings(*, require_webhook: bool = True) -> Settings:
    """Read settings from the environment, failing fast on missing values.

    ``require_webhook=False`` is used by the long-polling dev entrypoint, where
    the webhook variables are irrelevant.
    """
    webhook_path = os.environ.get("WEBHOOK_PATH", "/webhook").strip() or "/webhook"
    if not webhook_path.startswith("/"):
        webhook_path = "/" + webhook_path

    return Settings(
        bot_token=_require("BOT_TOKEN"),
        moderation_chat_id=_require_int("MODERATION_CHAT_ID"),
        target_chat_id=_require_int("TARGET_CHAT_ID"),
        webhook_host=_require("WEBHOOK_HOST") if require_webhook else "",
        webhook_path=webhook_path,
        webhook_secret_token=(
            _require("WEBHOOK_SECRET_TOKEN")
            if require_webhook
            else os.environ.get("WEBHOOK_SECRET_TOKEN", "")
        ),
        web_server_host=os.environ.get("WEB_SERVER_HOST", "0.0.0.0").strip(),
        web_server_port=int(os.environ.get("WEB_SERVER_PORT", "8080")),
    )
