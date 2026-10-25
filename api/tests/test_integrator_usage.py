"""Per-key usage history for integrators (GET /v1/auth/usage)."""

import uuid

from fastapi.testclient import TestClient

from api.app.core.auth import APIKeyRecord
from api.app.features.query.querylog import log_query
from api.app.main import app
from db import get_conn

client = TestClient(app)


def test_usage_counts_this_keys_questions_per_day(monkeypatch):
    monkeypatch.setenv("API_KEYS", "")
    email = f"usage-{uuid.uuid4().hex[:8]}@example.com"
    key = client.post(
        "/v1/auth/register", json={"name": "Test", "email": email, "use_case": "tests"}
    ).json()["api_key"]
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM api_keys WHERE owner_email = %s", (email,))
        key_id = cur.fetchone()[0]
    conn.close()
    try:
        record = APIKeyRecord(key_id, "Test", email, "free", key[:8] + "...")
        other = APIKeyRecord(str(uuid.uuid4()), "Other", None, "free", key[:8] + "...")
        log_query("Question ?", "fr", None, False, 5, 900, record)
        log_query("Hors sujet", "fr", None, True, 0, 300, record)
        log_query("Même préfixe, autre clé", "fr", None, False, 5, 900, other)

        resp = client.get("/v1/auth/usage?days=7", headers={"X-API-Key": key})
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert len(data["days"]) == 7
        assert data["days"][-1]["questions"] == 2
        assert data["days"][-1]["off_topic"] == 1
        assert client.get("/v1/auth/usage").status_code == 401
    finally:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_queries WHERE api_key_id IN (%s, %s)", (key_id, other.id))
            cur.execute("DELETE FROM api_keys WHERE owner_email = %s", (email,))
        conn.commit()
        conn.close()
