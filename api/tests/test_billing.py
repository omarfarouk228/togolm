"""Paid plans through PayGate Global."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app.features.billing import paygate, service
from api.app.main import app
from db import get_conn

client = TestClient(app)
ADMIN = "test-admin-secret"


@pytest.fixture
def priced(monkeypatch):
    """The dev plan for sale at 5,000 FCFA, set like the admin does."""
    monkeypatch.setenv("API_SECRET_KEY", ADMIN)
    monkeypatch.setenv("PAYGATE_API_KEY", "test")
    resp = client.put(
        "/v1/admin/billing/plans/dev",
        json={"label": "Développeur", "monthly_fcfa": 5000, "active": True},
        headers={"X-Admin-Key": ADMIN},
    )
    assert resp.status_code == 200
    yield
    client.put(
        "/v1/admin/billing/plans/dev",
        json={"label": "Développeur", "monthly_fcfa": None, "active": False},
        headers={"X-Admin-Key": ADMIN},
    )


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("API_KEYS", "")
    email = f"billing-{uuid.uuid4().hex[:8]}@example.com"
    api_key = client.post(
        "/v1/auth/register", json={"name": "Test", "email": email, "use_case": "tests"}
    ).json()["api_key"]
    yield api_key, email
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM api_keys WHERE owner_email = %s", (email,))
    conn.commit()
    conn.close()


def test_phone_numbers_are_normalized():
    assert service.normalize_phone("+228 90 12 34 56") == "90123456"
    assert service.normalize_phone("90-12-34-56") == "90123456"
    with pytest.raises(service.BillingError):
        service.normalize_phone("12345")


def test_plans_are_edited_from_the_admin(priced):
    data = client.get("/v1/billing/plans").json()
    assert data["available"] is True
    assert data["plans"]["dev"]["monthly_fcfa"] == 5000
    assert "institution" not in data["plans"]  # seeded inactive and unpriced
    admin = client.get("/v1/admin/billing/plans", headers={"X-Admin-Key": ADMIN}).json()
    assert {p["plan"] for p in admin["plans"]} >= {"dev", "institution"}
    bad = client.put(
        "/v1/admin/billing/plans/institution",
        json={"label": "Institution", "active": True},
        headers={"X-Admin-Key": ADMIN},
    )
    assert bad.status_code == 422  # for sale without a price
    assert client.get("/v1/admin/billing/plans").status_code == 401


def test_checkout_then_verified_payment_upgrades_the_key(priced, key):
    api_key, email = key
    headers = {"X-API-Key": api_key}

    with patch.object(
        paygate, "request_payment", return_value={"tx_reference": "T1", "status": 0}
    ) as pay:
        resp = client.post(
            "/v1/billing/checkout",
            json={"plan": "dev", "months": 2, "phone": "+228 90 12 34 56", "network": "tmoney"},
            headers=headers,
        )
    assert resp.status_code == 202
    identifier = resp.json()["identifier"]
    assert pay.call_args.args[:4] == ("90123456", 10000, identifier, "TMONEY")

    # The unsigned callback alone changes nothing: PayGate still says pending.
    with patch.object(paygate, "payment_status", return_value={"status": 2}):
        client.post(
            "/v1/billing/paygate/callback", json={"identifier": identifier, "amount": 10000}
        )
        assert (
            client.get(f"/v1/billing/payments/{identifier}", headers=headers).json()["status"]
            == "pending"
        )
    assert client.get("/v1/auth/me", headers=headers).json()["plan"] == "free"

    paid = {
        "status": 0,
        "payment_reference": "REF",
        "payment_method": "T-Money",
        "tx_reference": "T1",
    }
    with patch.object(paygate, "payment_status", return_value=paid):
        client.post("/v1/billing/paygate/callback", json={"identifier": identifier})
    assert client.get("/v1/auth/me", headers=headers).json()["plan"] == "dev"
    payments = client.get("/v1/admin/billing/payments", headers={"X-Admin-Key": ADMIN}).json()
    paid_row = next(p for p in payments["payments"] if p["identifier"] == identifier)
    assert (paid_row["status"], paid_row["amount"], paid_row["owner_email"]) == (
        "paid",
        10000,
        email,
    )

    conn = get_conn()
    with conn.cursor() as cur:  # past the paid period the key is free again
        cur.execute(
            "UPDATE api_keys SET plan_expires_at = NOW() - interval '1 day' WHERE owner_email = %s",
            (email,),
        )
    conn.commit()
    conn.close()
    assert client.get("/v1/auth/me", headers=headers).json()["plan"] == "free"


def test_checkout_unavailable_without_prices(key):
    resp = client.post(
        "/v1/billing/checkout",
        json={"plan": "dev", "phone": "90123456", "network": "FLOOZ"},
        headers={"X-API-Key": key[0]},
    )
    assert resp.status_code == 503


def test_key_rotation_keeps_the_account_and_kills_the_old_key(priced, key, monkeypatch):
    api_key, email = key
    # Non-empty, so an unknown key is refused instead of passing as a dev key.
    monkeypatch.setenv("API_KEYS", "only-this-env-key")
    with patch.object(paygate, "request_payment", return_value={"tx_reference": "T2", "status": 0}):
        identifier = client.post(
            "/v1/billing/checkout",
            json={"plan": "dev", "months": 1, "phone": "90123456", "network": "FLOOZ"},
            headers={"X-API-Key": api_key},
        ).json()["identifier"]

    rotated = client.post("/v1/auth/keys/rotate", headers={"X-API-Key": api_key})
    assert rotated.status_code == 200
    new_key = rotated.json()["api_key"]
    assert new_key != api_key

    assert client.get("/v1/auth/me", headers={"X-API-Key": api_key}).status_code == 401
    me = client.get("/v1/auth/me", headers={"X-API-Key": new_key}).json()
    assert me["email"] == email
    # Payments hang on the account, so the new key still sees them.
    mine = client.get("/v1/billing/payments", headers={"X-API-Key": new_key}).json()["items"]
    assert [p["identifier"] for p in mine] == [identifier]
    assert "owner_email" not in mine[0]


def test_payment_history_needs_a_key():
    assert client.get("/v1/billing/payments").status_code == 401
