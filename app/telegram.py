"""Telegram notification sender."""

import logging

import requests

from . import config

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID)


def send(message: str) -> bool:
    if not enabled():
        logger.debug("Telegram not configured, skipping: %s", message)
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        # Never log str(e) here: the request URL contains the bot token.
        status = getattr(getattr(e, "response", None), "status_code", None)
        detail = ""
        if getattr(e, "response", None) is not None:
            try:
                detail = e.response.json().get("description", "")
            except ValueError:
                pass
        logger.error("Telegram send failed: %s %s (%s)",
                     status or "network error", detail, type(e).__name__)
        return False
