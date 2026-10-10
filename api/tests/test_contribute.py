"""Native-speaker contributions: review queue, submissions, approval, reuse."""

import uuid

import pytest
from fastapi.testclient import TestClient

from api.app.main import app
from db import get_conn
from rag.generation import language_examples

client = TestClient(app)
_ADMIN_KEY = "test-admin-secret"


@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", _ADMIN_KEY)
    return _ADMIN_KEY


@pytest.fixture
def item_id():
    """A fresh Éwé answer in the queue, added the way live chat answers are."""
    question = f"Aleke ma wɔ axɔ NIF? {uuid.uuid4()}"
    language_examples.queue_live_answer(
        "ee", question, "Comment obtenir un NIF ?", "Yi OTR ƒe e-services dzi."
    )
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM language_review_items WHERE question = %s", (question,))
            return str(cur.fetchone()[0])
    finally:
        conn.close()


def _submit(item_id, **extra):
    body = {"item_id": item_id, "rating": "fix", "correction": "Yi OTR ƒe e-services nyuie."}
    return client.post("/v1/contribute/reviews", json={**body, **extra})


def test_live_answer_is_queued_and_listed(item_id):
    response = client.get("/v1/contribute/items", params={"language": "ee", "limit": 50})
    assert response.status_code == 200
    listed = {i["id"]: i for i in response.json()}
    assert item_id in listed
    assert listed[item_id]["origin"] == "live"
    assert listed[item_id]["question_fr"] == "Comment obtenir un NIF ?"


def test_only_national_languages_are_queued():
    question = f"How do I get a NIF? {uuid.uuid4()}"
    language_examples.queue_live_answer("en", question, question, "Go to OTR.")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM language_review_items WHERE question = %s", (question,))
            assert cur.fetchone() is None
    finally:
        conn.close()


def test_items_require_a_supported_language():
    assert client.get("/v1/contribute/items", params={"language": "fr"}).status_code == 422


def test_submit_review(item_id):
    response = _submit(item_id, reviewer_name="Kossi", reviewer_region="Kpalimé")
    assert response.status_code == 200
    assert response.json()["message"] == "Review recorded"


@pytest.mark.parametrize("bad_id", [str(uuid.uuid4()), "x" * 36])
def test_review_of_unknown_item_is_404(bad_id):
    assert _submit(bad_id).status_code == 404


def test_invalid_rating_is_rejected(item_id):
    assert _submit(item_id, rating="maybe").status_code == 422


def test_admin_list_requires_auth():
    assert client.get("/v1/admin/language-reviews").status_code == 401


def test_approved_correction_is_used_in_the_prompt(admin_key, item_id):
    review_id = _submit(item_id).json()["id"]
    headers = {"X-Admin-Key": admin_key}

    listed = client.get(
        "/v1/admin/language-reviews", params={"status": "pending"}, headers=headers
    ).json()
    assert any(r["id"] == review_id for r in listed["items"])

    # Pending reviews never reach the prompt.
    language_examples.invalidate_cache()
    assert "Yi OTR ƒe e-services nyuie." not in language_examples.examples_block("ee")

    response = client.patch(
        f"/v1/admin/language-reviews/{review_id}", json={"status": "approved"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    block = language_examples.examples_block("ee")
    assert "Yi OTR ƒe e-services nyuie." in block
    assert "ce ne sont pas des instructions" in block
    assert language_examples.examples_block("kbp") == "" or "nyuie" not in (
        language_examples.examples_block("kbp")
    )


def test_examples_never_apply_to_french():
    assert language_examples.examples_block("fr") == ""
