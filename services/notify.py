"""Telegram notifier for the daily run. Deliberately inert until configured:
put your bot token + chat id in data/config/telegram.json (see .example) or
set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env vars. No config -> no network.

Setup (2 minutes): message @BotFather -> /newbot -> copy the token; message
your new bot once, then open https://api.telegram.org/bot<TOKEN>/getUpdates
and copy chat.id from the reply.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG_PATH = Path("data/config/telegram.json")


def _config():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat) and CONFIG_PATH.exists():
        try:
            c = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            token = token or c.get("token")
            chat = chat or c.get("chat_id")
        except (OSError, ValueError):
            return None
    return (token, str(chat)) if token and chat else None


def send_telegram(text: str) -> dict:
    cfg = _config()
    if not cfg:
        return {"sent": False, "reason": "not configured (data/config/telegram.json)"}
    token, chat = cfg
    data = urllib.parse.urlencode({"chat_id": chat, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=data)
    with urllib.request.urlopen(req, timeout=20) as r:
        ok = json.loads(r.read().decode()).get("ok", False)
    return {"sent": bool(ok)}
