"""Generation health: answers silently falling back to extracts must be visible."""

import itertools
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.app.main import app
from rag.generation import health

client = TestClient(app)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, k, v):
        self.store[k] = str(v)

    def get(self, k):
        return self.store.get(k)

    def pipeline(self):
        outer = self

        class P:
            def set(self, k, v):
                outer.set(k, v)

            def execute(self):
                pass

        return P()


def test_short_cause_extracts_the_api_status():
    err = Exception(
        "402 RESOURCE_EXHAUSTED. {'error': {'message': 'Your prepayment credits are depleted.'}}"
    )
    assert health.short_cause(err) == "402 RESOURCE_EXHAUSTED"
    assert health.short_cause(ValueError("boom")) == "ValueError"


def test_status_follows_the_latest_outcome():
    fake = FakeRedis()
    # Logging reads the clock too, so use an ever-increasing counter.
    with (
        patch.object(health, "_redis", return_value=fake),
        patch.object(health.time, "time", side_effect=itertools.count(100, 100)),
    ):
        assert health.status()["status"] == "unknown"
        health.record_success()
        assert health.status()["status"] == "ok"
        health.record_failure(Exception("404 NOT_FOUND model retired"))
        degraded = health.status()
        assert degraded["status"] == "degraded" and degraded["cause"] == "404 NOT_FOUND"
        health.record_success()
        recovered = health.status()
        assert recovered["status"] == "ok" and recovered["cause"] is None


def test_redis_down_is_reported_as_unknown_not_an_error():
    broken = MagicMock()
    broken.get.side_effect = ConnectionError("down")
    with patch.object(health, "_redis", return_value=broken):
        assert health.status()["status"] == "unknown"


def test_build_answer_records_the_failure_before_falling_back():
    from rag.generation import chains

    with (
        patch.object(chains, "gemini_available", return_value=True),
        patch.object(chains, "_generate_answer", side_effect=Exception("402 RESOURCE_EXHAUSTED")),
        patch.object(chains.generation_health, "record_failure") as failed,
    ):
        chains.build_answer("question ?", [])
    failed.assert_called_once()


def test_health_generation_endpoint():
    with patch(
        "rag.generation.health.status",
        return_value={"status": "degraded", "cause": "402 RESOURCE_EXHAUSTED"},
    ):
        response = client.get("/health/generation")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
