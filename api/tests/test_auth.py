"""
Unit tests for API key authentication (api.app.auth).

These tests verify the X-API-Key header behaviour without hitting the DB.
Routes are tested via /v1/categories (lightweight, no DB needed when mocked).
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

# Patch the DB-hitting route so auth tests don't need a real PostgreSQL
_CATEGORIES_PATCH = patch(
    "api.app.routers.corpus.get_conn",
    side_effect=Exception("Should not reach DB in auth tests"),
)


class TestAuthAnonymous:
    def test_no_key_allowed_on_categories(self):
        """Anonymous access is permitted (rate-limited, but not blocked)."""
        resp = client.get("/v1/categories")
        # /categories doesn't hit DB, so no patch needed
        assert resp.status_code == 200

    def test_no_key_allowed_on_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestAuthWithKeys:
    def test_valid_key_accepted(self, with_api_keys):
        resp = client.get("/v1/categories", headers={"X-API-Key": "valid-test-key"})
        assert resp.status_code == 200

    def test_another_valid_key_accepted(self, with_api_keys):
        resp = client.get("/v1/categories", headers={"X-API-Key": "another-key"})
        assert resp.status_code == 200

    def test_invalid_key_returns_401(self, with_api_keys):
        resp = client.get("/v1/categories", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["detail"]

    def test_empty_key_returns_401(self, with_api_keys):
        resp = client.get("/v1/categories", headers={"X-API-Key": ""})
        assert resp.status_code == 401

    def test_dev_mode_accepts_any_key(self, no_api_keys):
        """When API_KEYS is empty, every key is accepted (dev mode)."""
        resp = client.get("/v1/categories", headers={"X-API-Key": "whatever"})
        assert resp.status_code == 200

    def test_dev_mode_accepts_no_key(self, no_api_keys):
        resp = client.get("/v1/categories")
        assert resp.status_code == 200


class TestAuthOnQueryEndpoint:
    def test_invalid_key_blocks_query(self, with_api_keys):
        resp = client.post(
            "/v1/query",
            json={"question": "Question test ?"},
            headers={"X-API-Key": "bad-key"},
        )
        assert resp.status_code == 401

    def test_valid_key_reaches_query(self, with_api_keys):
        with (
            patch("api.app.routers.query.retrieve", return_value=[]),
            patch("api.app.services.rag.build_answer", return_value="OK"),
        ):
            resp = client.post(
                "/v1/query",
                json={"question": "Question valide ?"},
                headers={"X-API-Key": "valid-test-key"},
            )
        assert resp.status_code == 200
