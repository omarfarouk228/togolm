"""
Unit tests for /search, /documents, and /documents/{id} endpoints.

DB calls are mocked — no real PostgreSQL needed.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SEARCH_ROW = (
    "aaaaaaaa-0000-0000-0000-000000000001",  # id
    "jo.gouv.tg",                            # source
    "https://jo.gouv.tg/loi-1",             # url
    "Loi de finances 2025",                  # title
    "Le budget de l'État togolais pour 2025 s'élève à 2 400 milliards de FCFA.",  # clean_content
    "legal",                                 # category  ← column 5
    0.87,                                    # score     ← column 6
)


def _make_search_conn(rows, count=1):
    """Mock psycopg2 connection for search queries."""
    mock_cur = MagicMock()
    mock_cur.__enter__ = lambda s: s
    mock_cur.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = rows
    mock_cur.fetchone.return_value = (count,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn


# ---------------------------------------------------------------------------
# GET /v1/search
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    def test_returns_expected_shape(self):
        with patch("api.app.routers.documents.get_conn", return_value=_make_search_conn([_SEARCH_ROW])):
            resp = client.get("/v1/search?q=budget+togo")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "total" in data
        assert "query" in data
        assert data["query"] == "budget togo"

    def test_category_is_populated_from_db(self):
        """SearchResult.category must come from the DB row, not be hardcoded None."""
        with patch("api.app.routers.documents.get_conn", return_value=_make_search_conn([_SEARCH_ROW])):
            resp = client.get("/v1/search?q=budget")
        result = resp.json()["results"][0]
        assert result["category"] == "legal"

    def test_score_is_populated_correctly(self):
        """Score is at column index 6 after adding category at index 5."""
        with patch("api.app.routers.documents.get_conn", return_value=_make_search_conn([_SEARCH_ROW])):
            resp = client.get("/v1/search?q=budget")
        result = resp.json()["results"][0]
        assert result["score"] == pytest.approx(0.87, abs=0.001)

    def test_source_and_url_populated(self):
        with patch("api.app.routers.documents.get_conn", return_value=_make_search_conn([_SEARCH_ROW])):
            resp = client.get("/v1/search?q=budget")
        result = resp.json()["results"][0]
        assert result["source"] == "jo.gouv.tg"
        assert result["url"] == "https://jo.gouv.tg/loi-1"

    def test_empty_results(self):
        with patch("api.app.routers.documents.get_conn", return_value=_make_search_conn([], count=0)):
            resp = client.get("/v1/search?q=inexistant")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_query_too_short_rejected(self):
        resp = client.get("/v1/search?q=x")
        assert resp.status_code == 422

    def test_source_filter_passes_param_to_db(self):
        mock_conn = _make_search_conn([_SEARCH_ROW])
        with patch("api.app.routers.documents.get_conn", return_value=mock_conn):
            resp = client.get("/v1/search?q=budget&source=jo.gouv.tg")
        assert resp.status_code == 200
        executed_params = mock_conn.cursor.return_value.execute.call_args_list
        all_params = [str(c) for c in executed_params]
        assert any("jo.gouv.tg" in p for p in all_params)

    def test_category_filter_passes_param_to_db(self):
        mock_conn = _make_search_conn([_SEARCH_ROW])
        with patch("api.app.routers.documents.get_conn", return_value=mock_conn):
            resp = client.get("/v1/search?q=budget&category=legal")
        assert resp.status_code == 200
        executed_params = mock_conn.cursor.return_value.execute.call_args_list
        all_params = [str(c) for c in executed_params]
        assert any("legal" in p for p in all_params)

    def test_multiple_results_all_have_category(self):
        row2 = (
            "bbbbbbbb-0000-0000-0000-000000000002",
            "service-public.gouv.tg",
            None,
            "Démarches administratives",
            "Pour obtenir un acte de naissance au Togo...",
            "administrative",
            0.72,
        )
        with patch(
            "api.app.routers.documents.get_conn",
            return_value=_make_search_conn([_SEARCH_ROW, row2], count=2),
        ):
            resp = client.get("/v1/search?q=togo")
        results = resp.json()["results"]
        assert len(results) == 2
        assert results[0]["category"] == "legal"
        assert results[1]["category"] == "administrative"

    def test_null_category_in_db_returns_none(self):
        row_no_cat = list(_SEARCH_ROW)
        row_no_cat[5] = None  # category is NULL in DB
        with patch(
            "api.app.routers.documents.get_conn",
            return_value=_make_search_conn([tuple(row_no_cat)]),
        ):
            resp = client.get("/v1/search?q=budget")
        result = resp.json()["results"][0]
        assert result["category"] is None
