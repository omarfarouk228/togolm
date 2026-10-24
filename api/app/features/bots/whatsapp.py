"""
WhatsApp bot webhook (Meta WhatsApp Cloud API): /v1/bots/whatsapp/webhook.

Setup: a Meta Business account with a WhatsApp phone number, then in the API's
environment WHATSAPP_TOKEN (permanent access token), WHATSAPP_PHONE_NUMBER_ID,
WHATSAPP_APP_SECRET (signs deliveries, X-Hub-Signature-256) and
WHATSAPP_VERIFY_TOKEN (any string, also typed in Meta's webhook settings; Meta
checks it with a GET). Subscribe the webhook to the "messages" field.

Users write first, so replies are free-form messages inside WhatsApp's 24-hour
customer service window: no message templates needed.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from api.app.features.bots import core

logger = logging.getLogger("togolm.bots")
router = APIRouter(tags=["Bots"], include_in_schema=False)

GRAPH = "https://graph.facebook.com/v21.0"
MAX_AUDIO_BYTES = 10 * 1024 * 1024


def _configured() -> bool:
    return all(
        os.getenv(name)
        for name in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_APP_SECRET")
    )


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ['WHATSAPP_TOKEN']}"}


def send(to: str, texts: list[str]) -> None:
    url = f"{GRAPH}/{os.environ['WHATSAPP_PHONE_NUMBER_ID']}/messages"
    for text in texts:
        httpx.post(
            url,
            headers=_headers(),
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text, "preview_url": False},
            },
            timeout=30,
        )


def _download_media(media_id: str) -> tuple[bytes, str] | None:
    info = httpx.get(f"{GRAPH}/{media_id}", headers=_headers(), timeout=30).json()
    if not info.get("url") or int(info.get("file_size") or 0) > MAX_AUDIO_BYTES:
        return None
    response = httpx.get(info["url"], headers=_headers(), timeout=60)
    if response.status_code != 200:
        return None
    return response.content, (info.get("mime_type") or "audio/ogg").split(";")[0]


def process_message(message: dict) -> None:
    sender = message.get("from")
    if not sender or not core.first_delivery("whatsapp", message.get("id", "")):
        return
    try:
        if message.get("type") == "text":
            replies = core.handle_text(
                "whatsapp", sender, (message.get("text") or {}).get("body", ""), "whatsapp"
            )
        elif message.get("type") == "audio":
            media = _download_media((message.get("audio") or {}).get("id", ""))
            replies = (
                core.handle_voice(
                    "whatsapp", sender, media[1], base64.b64encode(media[0]).decode(), "whatsapp"
                )
                if media
                else [core.VOICE_FAILED]
            )
        else:
            replies = [core.to_whatsapp(core.WELCOME)]
        send(sender, replies)
    except Exception:
        logger.exception("WhatsApp message failed")


def signature_valid(body: bytes, signature: str | None) -> bool:
    secret = os.getenv("WHATSAPP_APP_SECRET", "").encode()
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(signature or "", expected)


@router.get("/bots/whatsapp/webhook")
def whatsapp_verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and expected and secrets.compare_digest(token, expected):
        return PlainTextResponse(challenge)
    raise HTTPException(status_code=403)


@router.post("/bots/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    if not _configured():
        raise HTTPException(status_code=404)
    body = await request.body()
    if not signature_valid(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403)
    payload = await request.json()
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for message in (change.get("value") or {}).get("messages", []):
                background_tasks.add_task(process_message, message)
    return {"ok": True}
