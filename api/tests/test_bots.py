"""Telegram and WhatsApp bots: formatting, commands, quota, webhook security."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app.features.bots import core, telegram, whatsapp
from api.app.main import app

client = TestClient(app)


class FakeRedis:
    def __init__(self):
        self.kv, self.lists = {}, {}

    def get(self, k):
        return self.kv.get(k)

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.kv:
            return None
        self.kv[k] = str(v)
        return True

    def incr(self, k):
        self.kv[k] = str(int(self.kv.get(k, 0)) + 1)
        return int(self.kv[k])

    def lrange(self, k, start, end):
        return list(self.lists.get(k, []))

    def rpush(self, k, v):
        self.lists.setdefault(k, []).append(v)

    def ltrim(self, k, start, end):
        self.lists[k] = self.lists.get(k, [])[start:]

    def delete(self, k):
        self.lists.pop(k, None)

    def expire(self, k, ttl):
        pass

    def pipeline(self):
        outer, results = self, []

        class Pipe:
            def __getattr__(self, name):
                def call(*args, **kwargs):
                    results.append(getattr(outer, name)(*args, **kwargs))
                    return self

                return call

            def execute(self):
                return results

        return Pipe()


@pytest.fixture
def fake_redis():
    fake = FakeRedis()
    with patch.object(core, "_redis", return_value=fake):
        yield fake


def test_markdown_is_converted_for_each_channel():
    md = "### Étapes\n* **Déposer** le dossier & payer\n[Source](https://cfe.tg/a)"
    assert core.to_telegram_html(md) == (
        "<b>Étapes</b>\n• <b>Déposer</b> le dossier &amp; payer\n"
        '<a href="https://cfe.tg/a">Source</a>'
    )
    assert (
        core.to_whatsapp(md)
        == "*Étapes*\n• *Déposer* le dossier & payer\nSource (https://cfe.tg/a)"
    )


def test_answer_rendering_adds_sources_and_splits_long_texts():
    answer = core.Answer("Réponse.", [{"title": "Décret 2026-011", "url": "https://jo.gouv.tg/x"}])
    (message,) = core.render(answer, "html")
    assert message.endswith('<b>Sources</b>\n• <a href="https://jo.gouv.tg/x">Décret 2026-011</a>')
    long = core.Answer("\n\n".join(["mot " * 300] * 6), [])
    parts = core.render(long, "whatsapp")
    assert len(parts) > 1
    assert all(len(p) <= core.MAX_MESSAGE_CHARS for p in parts)


def test_commands_set_language_and_reset_history(fake_redis):
    assert core.handle_text("telegram", "42", "/start", "html")[0].startswith("Bonjour")
    assert "éwé" in core.handle_text("telegram", "42", "/ee", "html")[0]
    assert core.get_language("telegram", "42") == "ee"
    core._remember("telegram", "42", "Question ?", "Réponse.")
    assert len(core._history("telegram", "42")) == 2
    core.handle_text("telegram", "42", "/nouveau", "html")
    assert core._history("telegram", "42") == []


def test_questions_are_answered_within_the_daily_quota(fake_redis):
    answer = core.Answer("Le taux est de **5,3637 %**.", [])
    with (
        patch.object(core, "_ask", return_value=answer) as ask,
        patch.object(core, "DAILY_LIMIT", 1),
    ):
        assert core.handle_text("whatsapp", "228900", "Taux légal 2026 ?", "whatsapp") == [
            "Le taux est de *5,3637 %*."
        ]
        assert "limite" in core.handle_text("whatsapp", "228900", "Encore ?", "whatsapp")[0]
    ask.assert_called_once()


def test_pipeline_failure_gets_a_polite_reply(fake_redis):
    with patch.object(core, "_ask", side_effect=RuntimeError("down")):
        assert core.handle_text("telegram", "1", "Question ?", "html") == [core.FAILURE]


def test_telegram_webhook_requires_its_secret(monkeypatch):
    update = {"update_id": 1, "message": {"chat": {"id": 7}, "text": "Bonjour"}}
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert client.post("/v1/bots/telegram/webhook", json=update).status_code == 404

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "s3cret")
    bad = {"X-Telegram-Bot-Api-Secret-Token": "nope"}
    assert client.post("/v1/bots/telegram/webhook", json=update, headers=bad).status_code == 403

    with patch.object(telegram, "process_update") as process:
        ok = {"X-Telegram-Bot-Api-Secret-Token": "s3cret"}
        assert client.post("/v1/bots/telegram/webhook", json=update, headers=ok).status_code == 200
    process.assert_called_once_with(update)


def test_whatsapp_webhook_verification_and_signature(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-me")
    params = {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"}
    assert client.get("/v1/bots/whatsapp/webhook", params=params).text == "42"
    params["hub.verify_token"] = "wrong"
    assert client.get("/v1/bots/whatsapp/webhook", params=params).status_code == 403

    for name, value in (
        ("WHATSAPP_TOKEN", "token"),
        ("WHATSAPP_PHONE_NUMBER_ID", "123"),
        ("WHATSAPP_APP_SECRET", "app-secret"),
    ):
        monkeypatch.setenv(name, value)
    message = {"from": "22890000000", "id": "wamid.1", "type": "text", "text": {"body": "Salut"}}
    body = json.dumps({"entry": [{"changes": [{"value": {"messages": [message]}}]}]}).encode()
    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()

    bad = {"X-Hub-Signature-256": "sha256=0", "Content-Type": "application/json"}
    assert client.post("/v1/bots/whatsapp/webhook", content=body, headers=bad).status_code == 403
    with patch.object(whatsapp, "process_message") as process:
        good = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}
        assert (
            client.post("/v1/bots/whatsapp/webhook", content=body, headers=good).status_code == 200
        )
    process.assert_called_once_with(message)
