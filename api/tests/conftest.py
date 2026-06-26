"""
Shared pytest fixtures for TogoLM API tests.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="session")
def disable_rate_limit():
    """Patch Redis to always return count=1 so rate limits never trigger.

    Keeps check_rate_limit running (auth sub-dep get_api_key still executes)
    while avoiding 429s caused by the shared anon IP across the test session.
    """
    mock_redis = MagicMock()
    mock_redis.incr.return_value = 1
    mock_redis.pipeline.return_value.execute.return_value = []
    with patch("api.app.core.rate_limit._get_redis", return_value=mock_redis):
        yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Single TestClient shared across the session."""
    from api.app.main import app

    return TestClient(app)


@pytest.fixture
def fake_chunk():
    """A minimal RetrievedChunk for unit tests."""
    from rag.retrieval import RetrievedChunk

    return RetrievedChunk(
        title="Loi de finances 2025",
        url="https://jo.gouv.tg/loi-finances-2025",
        source="jo.gouv.tg",
        category="legal",
        content="Le budget de l'État togolais pour 2025 s'élève à 2 400 milliards de FCFA.",
        score=0.87,
    )


@pytest.fixture
def fake_chunk_long():
    """A chunk with content exceeding the 800-char truncation threshold."""
    from rag.retrieval import RetrievedChunk

    return RetrievedChunk(
        title="Document long",
        url=None,
        source="test",
        category="education",
        content="mot " * 300,  # 1 200 chars
        score=0.75,
    )


@pytest.fixture
def no_api_keys(monkeypatch):
    """Dev mode: API_KEYS is empty → all keys accepted."""
    monkeypatch.setenv("API_KEYS", "")


@pytest.fixture
def with_api_keys(monkeypatch):
    """Production mode: only 'valid-test-key' is accepted."""
    monkeypatch.setenv("API_KEYS", "valid-test-key,another-key")
