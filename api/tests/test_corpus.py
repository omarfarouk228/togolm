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


def test_stats_includes_sources():
    response = client.get("/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert len(data["sources"]) > 0
    first = data["sources"][0]
    assert "source" in first
    assert "documents" in first
    assert "chunks" in first


def test_list_documents():
    response = client.get("/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert "pages" in data
    assert data["total"] > 0


def test_list_documents_filter_by_source():
    response = client.get("/v1/documents?source=jo.gouv.tg&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert all(d["source"] == "jo.gouv.tg" for d in data["documents"])


def test_get_document_by_id():
    # Get any valid ID from the list
    list_resp = client.get("/v1/documents?page_size=1")
    doc_id = list_resp.json()["documents"][0]["id"]

    response = client.get(f"/v1/documents/{doc_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert "chunks" in data
    assert isinstance(data["chunks"], list)


def test_get_document_not_found():
    response = client.get("/v1/documents/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_search():
    response = client.get("/v1/search?q=budget+togo")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert data["query"] == "budget togo"
