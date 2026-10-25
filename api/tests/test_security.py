"""Security hardening: admin lockout, bounded feedback, website-only shortcuts."""

from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient

from api.app.features.admin import service as admin_service
from api.app.main import app

client = TestClient(app)


class FakeRedis:
    def __init__(self):
        self.data: dict[str, int] = {}

    def get(self, key):
        return self.data.get(key)

    def incr(self, key):
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def expire(self, key, seconds):
        return True


def test_admin_login_locks_an_ip_after_repeated_failures(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "the-real-admin-secret")
    fake = FakeRedis()
    with patch("api.app.core.rate_limit._get_redis", return_value=fake):
        for _ in range(admin_service._MAX_FAILS_PER_IP):
            assert client.post("/v1/admin/login", json={"key": "guess"}).status_code == 401
        # Locked, even with the right key, until the window ends.
        resp = client.post("/v1/admin/login", json={"key": "the-real-admin-secret"})
        assert resp.status_code == 429


def test_admin_tokens_are_not_signed_with_the_admin_password(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "the-real-admin-secret")
    monkeypatch.delenv("ADMIN_JWT_SECRET", raising=False)
    with patch("api.app.core.rate_limit._get_redis", return_value=FakeRedis()):
        token = client.post("/v1/admin/login", json={"key": "the-real-admin-secret"}).json()[
            "token"
        ]
    try:
        jwt.decode(token, "the-real-admin-secret", algorithms=["HS256"])
        signed_with_password = True
    except jwt.InvalidSignatureError:
        signed_with_password = False
    assert not signed_with_password
    admin_service.require_admin(f"Bearer {token}", None)  # still a valid admin token


def test_feedback_sources_must_be_web_links():
    body = {
        "category": "incorrect",
        "question": "q",
        "answer": "a",
        "sources": [{"title": "x", "url": "javascript:alert(1)"}],
    }
    assert client.post("/v1/feedback", json=body).status_code == 422
    body["sources"] = [{"title": "x", "url": "https://example.com"}] * 11
    assert client.post("/v1/feedback", json=body).status_code == 422
