import pytest
from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

_VALID_PAYLOAD = {
    "category": "incorrect",
    "question": "Quelle est la capitale du Togo ?",
    "answer": "La capitale du Togo est Kara.",
    "comment": "C'est Lomé, pas Kara.",
    "sources": [{"title": "Wikipedia Togo", "url": "https://fr.wikipedia.org/wiki/Togo"}],
}


def test_submit_feedback_returns_id():
    response = client.post("/v1/feedback", json=_VALID_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["message"]


def test_submit_feedback_missing_required_field():
    response = client.post("/v1/feedback", json={"category": "incorrect", "question": "x"})
    assert response.status_code == 422


def test_submit_feedback_unknown_category_falls_back_to_other():
    payload = {**_VALID_PAYLOAD, "category": "not_a_real_category", "comment": None}
    response = client.post("/v1/feedback", json=payload)
    assert response.status_code == 200


def test_submit_feedback_without_optional_fields():
    payload = {
        "category": "other",
        "question": "q",
        "answer": "a",
    }
    response = client.post("/v1/feedback", json=payload)
    assert response.status_code == 200


@pytest.mark.parametrize("field", ["question", "answer"])
def test_submit_feedback_rejects_oversized_fields(field):
    payload = {**_VALID_PAYLOAD, field: "x" * 10_000}
    response = client.post("/v1/feedback", json=payload)
    assert response.status_code == 422
