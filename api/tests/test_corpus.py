from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_categories():
    response = client.get("/v1/categories")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) > 0
    assert "administrative" in data["categories"]


def test_stats():
    response = client.get("/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert "languages" in data


def test_query_returns_answer():
    response = client.post("/v1/query", json={"question": "Comment créer une SARL au Togo ?"})
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "latency_ms" in data


def test_embed_returns_vector():
    response = client.post("/v1/embed", json={"text": "Test text"})
    assert response.status_code == 200
    data = response.json()
    assert "embedding" in data
    assert len(data["embedding"]) == 384
