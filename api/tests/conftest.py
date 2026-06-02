"""
Shared pytest fixtures for TogoLM API tests.
"""

import pytest
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.services.rag import RetrievedChunk


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Single TestClient shared across the session."""
    return TestClient(app)


@pytest.fixture
def fake_chunk() -> RetrievedChunk:
    """A minimal RetrievedChunk for unit tests."""
    return RetrievedChunk(
        title="Loi de finances 2025",
        url="https://jo.gouv.tg/loi-finances-2025",
        source="jo.gouv.tg",
        category="legal",
        content="Le budget de l'État togolais pour 2025 s'élève à 2 400 milliards de FCFA.",
        score=0.87,
    )


@pytest.fixture
def fake_chunk_long() -> RetrievedChunk:
    """A chunk with content exceeding the 800-char truncation threshold."""
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
