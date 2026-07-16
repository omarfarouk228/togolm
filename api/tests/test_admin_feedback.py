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
def sample_feedback_id(admin_key):
    response = client.post(
        "/v1/feedback",
        json={
            "category": "incorrect",
            "question": "Quelle est la capitale du Togo ?",
            "answer": "Kara",
            "comment": "C'est Lomé, pas Kara.",
        },
    )
    return response.json()["id"]


def test_list_feedback_requires_auth():
    response = client.get("/v1/admin/feedback")
    assert response.status_code == 401


def test_list_feedback_returns_submitted_entry(admin_key, sample_feedback_id):
    response = client.get("/v1/admin/feedback", headers={"X-Admin-Key": admin_key})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert any(item["id"] == sample_feedback_id for item in data["items"])


def test_list_feedback_filters_by_status(admin_key, sample_feedback_id):
    response = client.get(
        "/v1/admin/feedback",
        params={"status": "open"},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 200
    assert all(item["status"] == "open" for item in response.json()["items"])


def test_update_feedback_status(admin_key, sample_feedback_id):
    response = client.patch(
        f"/v1/admin/feedback/{sample_feedback_id}",
        json={"status": "reviewed"},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"


def test_update_feedback_invalid_status_rejected(admin_key, sample_feedback_id):
    response = client.patch(
        f"/v1/admin/feedback/{sample_feedback_id}",
        json={"status": "not_a_real_status"},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 400


def test_update_feedback_not_found(admin_key):
    response = client.patch(
        "/v1/admin/feedback/00000000-0000-0000-0000-000000000000",
        json={"status": "reviewed"},
        headers={"X-Admin-Key": admin_key},
    )
    assert response.status_code == 404


def test_update_feedback_requires_auth(sample_feedback_id):
    response = client.patch(
        f"/v1/admin/feedback/{sample_feedback_id}",
        json={"status": "reviewed"},
    )
    assert response.status_code == 401
