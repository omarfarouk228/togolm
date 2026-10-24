"""
POST /v1/alerts                    — Subscribe an e-mail address to a search (sends a confirmation link)
GET  /v1/alerts/confirm?token=     — Confirm it (link in the e-mail)
GET  /v1/alerts/unsubscribe?token= — Stop it (link in every digest)

Telegram and WhatsApp users subscribe from the bot (/alerte <mots>).
"""

import datetime
import html

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field

from api.app.features.alerts import service
from api.app.features.alerts.mail import email_configured, send_email

router = APIRouter(tags=["Alerts"])

DAILY_SIGNUPS_PER_IP = 5


class AlertRequest(BaseModel):
    email: EmailStr
    query: str = Field(..., min_length=3, max_length=200)
    category: str | None = Field(None, max_length=50)


def _page(title: str, message: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='fr'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<body style='font-family:system-ui,sans-serif;max-width:520px;margin:15vh auto;"
        "padding:0 20px;color:#0f172a'>"
        f"<h1 style='font-size:22px'>{html.escape(title)}</h1><p>{html.escape(message)}</p>"
        "<p><a href='https://togolm.com' style='color:#006a4e'>togolm.com</a></p></body></html>"
    )


def _within_signup_limit(ip: str) -> bool:
    from api.app.features.bots.core import _redis

    key = f"togolm:alerts:signups:{ip}:{datetime.date.today().isoformat()}"
    try:
        pipe = _redis().pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        return int(pipe.execute()[0]) <= DAILY_SIGNUPS_PER_IP
    except Exception:
        return True


@router.post("/alerts", status_code=202)
def subscribe(body: AlertRequest, request: Request):
    if not email_configured():
        raise HTTPException(status_code=503, detail="E-mail alerts are not available.")
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "")
    if not _within_signup_limit(ip.split(",")[0].strip()):
        raise HTTPException(status_code=429, detail="Too many sign-ups today.")
    try:
        sub = service.create("email", str(body.email).lower(), body.query, body.category)
    except service.AlertError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None
    link = f"{service.PUBLIC_API_URL}/v1/alerts/confirm?token={sub['token']}"
    send_email(
        str(body.email),
        f"Confirmez votre alerte TogoLM « {sub['query']} »",
        "Bonjour,\n\nVous avez demandé à recevoir chaque jour les nouveaux documents publics "
        f"togolais sur « {sub['query']} ».\n\nConfirmez en ouvrant ce lien :\n{link}\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\nTogoLM",
    )
    return {"status": "confirmation_sent"}


@router.get("/alerts/confirm", include_in_schema=False)
def confirm(token: str = Query(..., max_length=64)):
    if service.confirm(token):
        return _page("Alerte confirmée", "Vous recevrez les nouveaux documents chaque matin.")
    return _page("Lien invalide", "Cette alerte n'existe pas ou a été arrêtée.")


@router.get("/alerts/unsubscribe", include_in_schema=False)
def unsubscribe(token: str = Query(..., max_length=64)):
    service.unsubscribe(token)
    return _page("Alerte arrêtée", "Vous ne recevrez plus cette alerte.")
