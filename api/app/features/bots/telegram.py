"""
Telegram bot webhook: POST /v1/bots/telegram/webhook.

Setup (once, see scripts/bots/telegram_setup.py): create the bot with
@BotFather, set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET in the API's
environment, then register the webhook. Telegram signs each delivery with the
secret in X-Telegram-Bot-Api-Secret-Token.

The webhook answers 200 at once and the reply is built in the background
(answers take ~10 s; Telegram would otherwise retry the delivery).
"""

import base64
import logging
import os
import secrets

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from api.app.features.bots import core

logger = logging.getLogger("togolm.bots")
router = APIRouter(tags=["Bots"], include_in_schema=False)

API = "https://api.telegram.org"
MAX_VOICE_BYTES = 10 * 1024 * 1024


def _token() -> str:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def _call(method: str, **payload) -> dict:
    response = httpx.post(f"{API}/bot{_token()}/{method}", json=payload, timeout=30)
    return response.json()


def send(chat_id: int, texts: list[str]) -> None:
    for text in texts:
        result = _call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            link_preview_options={"is_disabled": True},
        )
        if not result.get("ok"):
            # Malformed HTML from an unusual answer: send it as plain text.
            _call("sendMessage", chat_id=chat_id, text=text)


def _download_voice(file_id: str) -> bytes | None:
    info = _call("getFile", file_id=file_id).get("result") or {}
    if not info.get("file_path") or info.get("file_size", 0) > MAX_VOICE_BYTES:
        return None
    response = httpx.get(f"{API}/file/bot{_token()}/{info['file_path']}", timeout=60)
    return response.content if response.status_code == 200 else None


def process_update(update: dict) -> None:
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if not chat_id or not core.first_delivery("telegram", str(update.get("update_id"))):
        return
    user_id = str(chat_id)
    try:
        _call("sendChatAction", chat_id=chat_id, action="typing")
        voice = message.get("voice") or message.get("audio")
        if voice:
            audio = _download_voice(voice["file_id"])
            replies = (
                core.handle_voice(
                    "telegram",
                    user_id,
                    voice.get("mime_type") or "audio/ogg",
                    base64.b64encode(audio).decode(),
                    "html",
                )
                if audio
                else [core.VOICE_FAILED]
            )
        elif message.get("text"):
            replies = core.handle_text("telegram", user_id, message["text"], "html")
        else:
            replies = [core.WELCOME]
        send(chat_id, replies)
    except Exception:
        logger.exception("Telegram update failed")


@router.post("/bots/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if not _token() or not expected:
        raise HTTPException(status_code=404)
    if not secrets.compare_digest(x_telegram_bot_api_secret_token or "", expected):
        raise HTTPException(status_code=403)
    background_tasks.add_task(process_update, await request.json())
    return {"ok": True}
