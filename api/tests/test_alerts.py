"""Alerts: e-mail double opt-in, bot commands, daily digests."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.features.alerts import service
from api.app.features.bots import core
from api.app.main import app
from db import get_conn

client = TestClient(app)


def _cleanup(target: str, url: str | None = None):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alert_subscriptions WHERE target = %s", (target,))
        if url:
            cur.execute("DELETE FROM documents WHERE url = %s", (url,))
    conn.commit()
    conn.close()


def test_email_alert_needs_confirmation_then_sends_new_matches(monkeypatch):
    from rag.indexation.ingestor import upsert_document

    email = f"alerte-{uuid.uuid4().hex[:8]}@example.com"
    url = f"https://dnccp.gouv.tg/documents/test-{uuid.uuid4()}"
    monkeypatch.setenv("EMAIL_SERVER_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAIL_FROM", "TogoLM <alertes@togolm.com>")
    try:
        with patch("api.app.features.alerts.router.send_email") as mailed:
            resp = client.post(
                "/v1/alerts", json={"email": email, "query": "passation informatique"}
            )
        assert resp.status_code == 202
        link = mailed.call_args.args[2]
        token = link.split("token=")[1].split()[0]

        conn = get_conn()
        with conn.cursor() as cur:
            upsert_document(
                cur,
                {
                    "source": "dnccp.gouv.tg",
                    "url": url,
                    "category": "economy",
                    "title": "Plan de passation 2026 : matériel informatique",
                    "raw_content": "Plan de passation des marchés de matériel informatique " * 5,
                    "clean_content": "Plan de passation des marchés de matériel informatique " * 5,
                },
            )
        conn.commit()
        conn.close()

        with patch.object(service, "_deliver") as delivered:
            service.send_digests()
        assert all(call.args[0]["target"] != email for call in delivered.call_args_list)

        assert "confirmée" in client.get(f"/v1/alerts/confirm?token={token}").text
        conn = get_conn()
        with conn.cursor() as cur:  # pretend it was created before the document
            cur.execute(
                "UPDATE alert_subscriptions SET created_at = NOW() - interval '1 day' "
                "WHERE target = %s",
                (email,),
            )
        conn.commit()
        conn.close()
        with patch.object(service, "_deliver") as delivered:
            service.send_digests()
        (sub, docs) = next(c.args for c in delivered.call_args_list if c.args[0]["target"] == email)
        assert [d["url"] for d in docs] == [url]

        assert "arrêtée" in client.get(f"/v1/alerts/unsubscribe?token={token}").text
        assert service.list_for("email", email) == []
    finally:
        _cleanup(email, url)


def test_email_alerts_unavailable_without_smtp(monkeypatch):
    monkeypatch.delenv("EMAIL_SERVER_HOST", raising=False)
    resp = client.post("/v1/alerts", json={"email": "a@example.com", "query": "concours"})
    assert resp.status_code == 503


def test_bot_alert_commands():
    chat = f"test-{uuid.uuid4().hex[:8]}"
    try:
        with patch.object(core, "_redis", side_effect=RuntimeError("no redis")):
            created = core.handle_text(
                "telegram", chat, "/alerte concours fonction publique", "html"
            )
            listed = core.handle_text("telegram", chat, "/alertes", "html")
            stopped = core.handle_text("telegram", chat, "/stopalertes", "html")
        assert "concours fonction publique" in created[0]
        assert "• concours fonction publique" in listed[0]
        assert stopped[0].startswith("1 alerte")
        assert service.list_for("telegram", chat) == []
    finally:
        _cleanup(chat)


def test_digest_formats():
    sub = {"query": "budget", "token": "tok"}
    docs = [{"title": "Loi de finances 2027", "url": "https://x.tg/a", "source": "x.tg"}]
    assert "<b>Alerte « budget »</b> : 1 nouveau document" in service.digest(sub, docs, "html")
    text = service.digest(sub, docs, "text")
    assert "https://x.tg/a" in text and "unsubscribe?token=tok" in text
