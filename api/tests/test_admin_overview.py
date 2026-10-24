import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api.app.features.admin import service
from api.app.main import app

client = TestClient(app)

_ADMIN_KEY = "test-admin-secret"


@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setenv("API_SECRET_KEY", _ADMIN_KEY)
    return _ADMIN_KEY


def test_overview_requires_auth():
    assert client.get("/v1/admin/overview").status_code in (401, 403)


def test_overview_shape(admin_key):
    response = client.get("/v1/admin/overview?days=7", headers={"X-Admin-Key": admin_key})
    assert response.status_code == 200
    data = response.json()

    assert data["generation"]["status"] in ("ok", "degraded", "unknown")
    assert data["corpus"]["documents"] > 0
    assert data["corpus"]["sources"] == len(data["sources"])
    assert {"open_feedback", "pending_reviews"} <= data["todo"].keys()

    assert len(data["traffic"]) == 7
    day = data["traffic"][-1]
    assert {"date", "queries", "latency_p50_ms", "latency_p90_ms", "requests"} <= day.keys()

    jo = next(s for s in data["sources"] if s["source"] == "jo.gouv.tg")
    assert jo["schedule"] == "weekly"
    assert jo["stale"] is False
    assert 0 <= jo["undated_pct"] <= 100


def test_crawl_results_are_listed_latest_first():
    r = MagicMock()
    r.hgetall.return_value = {
        "icilome": json.dumps({"spider": "icilome", "finished_at": "2026-10-24T06:38:00+00:00"}),
        "togofirst": json.dumps(
            {"spider": "togofirst", "finished_at": "2026-10-24T06:37:00+00:00"}
        ),
        "broken": "not json",
    }
    assert [c["spider"] for c in service._crawls(r)] == ["icilome", "togofirst"]


def test_chunk_counts_are_cached():
    r = MagicMock()
    r.get.return_value = None
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (10, 8)
    assert service.chunk_counts(conn, r) == (10, 8)
    r.set.assert_called_once()

    r.get.return_value = json.dumps([12, 12])
    conn = MagicMock()
    assert service.chunk_counts(conn, r) == (12, 12)
    conn.cursor.assert_not_called()
