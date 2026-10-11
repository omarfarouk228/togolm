import uuid

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

_ADMIN_KEY = "test-admin-secret"


@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", _ADMIN_KEY)
    return _ADMIN_KEY


@pytest.fixture
def created_key(admin_key):
    response = client.post(
        "/v1/admin/keys",
        json={"name": "Test", "email": f"keys-{uuid.uuid4().hex[:8]}@example.com"},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 201
    data = response.json()
    listing = client.get(
        "/v1/admin/keys",
        params={"page_size": 100},
        headers={"X-Admin-Key": admin_key},
    ).json()
    prefix = data["key_prefix"].removesuffix("...")
    key_id = next(item["id"] for item in listing["items"] if item["key_prefix"] == prefix)
    yield {"id": key_id, "api_key": data["api_key"]}
    client.delete(f"/v1/admin/keys/{key_id}", headers={"X-Admin-Key": admin_key})


def test_list_keys_requires_auth():
    assert client.get("/v1/admin/keys").status_code == 401


def test_list_keys_is_paginated(admin_key, created_key):
    response = client.get(
        "/v1/admin/keys",
        params={"page": 1, "page_size": 1},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert data["total"] >= 1
    assert len(data["items"]) == 1


def test_reset_key_issues_new_secret(admin_key, created_key):
    old = created_key["api_key"]
    response = client.post(
        f"/v1/admin/keys/{created_key['id']}/reset",
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 200
    new = response.json()["api_key"]
    assert new != old
    assert new.startswith("tgolm_")

    from api.app.core.auth import _lookup_db

    assert _lookup_db(old) is None
    assert _lookup_db(new) is not None


def test_reset_unknown_key_returns_404(admin_key):
    response = client.post(
        f"/v1/admin/keys/{uuid.uuid4()}/reset",
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 404


def test_reset_key_requires_auth(created_key):
    response = client.post(f"/v1/admin/keys/{created_key['id']}/reset")
    assert response.status_code == 401
