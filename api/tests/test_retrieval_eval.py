"""Weekly retrieval eval: metrics, regression flag, admin history endpoint."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app.main import app
from rag.evaluation import retrieval as ev
from rag.retrieval import RetrievedChunk

client = TestClient(app)


def _chunk(url: str) -> RetrievedChunk:
    return RetrievedChunk(title="Titre", url=url, source="s", category="c", content="x", score=0.8)


CASES = [
    {"question": "Comment obtenir un NIF ?", "expect": "otr\\.tg"},
    {"question": "Quel est le SMIG ?", "expect": "smig"},
]


def test_evaluate_computes_hit_rate_mrr_and_regression():
    answers = {
        "Comment obtenir un NIF ?": [_chunk("https://a.tg"), _chunk("https://otr.tg/nif")],
        "Quel est le SMIG ?": [_chunk("https://b.tg")],
    }
    with patch.object(ev, "run_retrieval", side_effect=lambda q, p, k: answers[q]):
        report = ev.evaluate(CASES, pause_s=0)
    assert report["hits"] == 1
    assert report["hit_rate"] == 0.5
    assert report["mrr"] == 0.25  # (1/2 + 0) / 2
    assert report["regression"] is True
    assert report["results"][0]["rank"] == 2


def test_cases_file_ships_with_the_repo():
    cases = ev.load_cases()
    assert len(cases) >= 10
    assert all({"question", "expect"} <= set(c) for c in cases)


def test_admin_eval_history_requires_auth():
    assert client.get("/v1/admin/eval/retrieval").status_code == 401


def test_admin_eval_history_returns_runs(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", "test-admin-secret")
    fake = MagicMock()
    fake.lrange.return_value = [json.dumps({"hit_rate": 1.0, "regression": False})]
    with patch("api.app.features.admin.service.get_redis", return_value=fake):
        response = client.get(
            "/v1/admin/eval/retrieval", headers={"X-Admin-Key": "test-admin-secret"}
        )
    assert response.status_code == 200
    assert response.json() == {"runs": [{"hit_rate": 1.0, "regression": False}]}
