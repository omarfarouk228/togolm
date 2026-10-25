"""Paid plans through PayGate Global."""

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.app.features.billing import paygate, service
from api.app.main import app
from db import get_conn

client = TestClient(app)
PLANS = json.dumps({"dev": {"label": "Développeur", "monthly_fcfa": 5000}})


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


def test_plans_come_from_configuration(monkeypatch):
    monkeypatch.setenv("BILLING_PLANS", PLANS)
    monkeypatch.setenv("PAYGATE_API_KEY", "test")
    data = client.get("/v1/billing/plans").json()
    assert data["available"] is True
    assert data["plans"]["dev"]["monthly_fcfa"] == 5000
    monkeypatch.delenv("BILLING_PLANS")
    assert client.get("/v1/billing/plans").json()["plans"] == {}


def test_checkout_then_verified_payment_upgrades_the_key(monkeypatch, key):
    api_key, email = key
    monkeypatch.setenv("BILLING_PLANS", PLANS)
    monkeypatch.setenv("PAYGATE_API_KEY", "test")
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

    conn = get_conn()
    with conn.cursor() as cur:  # past the paid period the key is free again
        cur.execute(
            "UPDATE api_keys SET plan_expires_at = NOW() - interval '1 day' WHERE owner_email = %s",
            (email,),
        )
    conn.commit()
    conn.close()
    assert client.get("/v1/auth/me", headers=headers).json()["plan"] == "free"


def test_checkout_unavailable_without_prices(monkeypatch, key):
    monkeypatch.delenv("BILLING_PLANS", raising=False)
    resp = client.post(
        "/v1/billing/checkout",
        json={"plan": "dev", "phone": "90123456", "network": "FLOOZ"},
        headers={"X-API-Key": key[0]},
    )
    assert resp.status_code == 503
