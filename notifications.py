from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, Final, Optional

import aiohttp

try:
    from config import CONFIG  # noqa: WPS433 (runtime import)
except Exception:  # pragma: no cover — config may be absent during unit tests
    CONFIG: Dict[str, Any] = {}

logger: Final[logging.Logger] = logging.getLogger("notifications")
logger.setLevel(logging.INFO)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_LEVEL_EMOJI: Dict[str, str] = {
    "INFO": "ℹ️",
    "WARN": "⚠️",
    "ALERT": "🚨",
}


def _get_token_and_chat(default_chat: Optional[str] = None) -> tuple[Optional[str], Optional[str]]:
    """Resolve credentials from CONFIG or env vars."""
    token = CONFIG.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = (
        default_chat
        or CONFIG.get("telegram_default_chat_id")
        or os.getenv("TELEGRAM_CHAT_ID")
    )
    return str(token) if token else None, str(chat) if chat else None


async def _post_json(url: str, data: Dict[str, Any]) -> None:
    """POST helper with short timeout & error logging."""
    timeout = aiohttp.ClientTimeout(total=4)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=data) as resp:
            if resp.status != 200:
                text = await resp.text()
                logger.warning("Telegram API responded %s: %s", resp.status, text)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
async def send_notification(
    chat_id: Optional[str],
    message: str,
    level: str = "INFO",
    *,
    parse_mode: str = "HTML",
    extra: Optional[Dict[str, Any]] = None,
) -> None:

    token, default_chat = _get_token_and_chat(chat_id)

    # Fallback to logging if we have no token
    if not token:
        logger.info("[%s] %s — no Telegram token, logged only", level, message)
        return

    chat_id = chat_id or default_chat
    if not chat_id:
        logger.warning("Telegram chat_id not provided — skipping send_notification")
        return

    prefix = _LEVEL_EMOJI.get(level.upper(), "")
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": f"{prefix} {message}",
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if extra is not None:
        payload["reply_markup"] = json.dumps(extra)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        await _post_json(url, payload)
        logger.debug("Notification sent to chat %s", chat_id)
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception as exc:  # pragma: no cover — network errors
        logger.exception("Failed to send Telegram notification: %s", exc)
        # Do not re‑raise: notification failure shouldn’t crash trading loop
