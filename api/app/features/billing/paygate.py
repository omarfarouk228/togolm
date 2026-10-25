"""
PayGate Global client (Togo mobile money: Flooz, T-Money).

From PayGate's integration guide (merchant dashboard, 2026-10-25):
- POST https://paygateglobal.com/api/v1/pay {auth_token, phone_number, amount,
  description, identifier, network: FLOOZ|TMONEY} -> {tx_reference, status}
  (0 recorded, 2 bad token, 4 bad parameters, 6 duplicate identifier). The
  customer then confirms on their phone.
- POST https://paygateglobal.com/api/v2/status {auth_token, identifier} ->
  {tx_reference, payment_reference, status, datetime, payment_method}
  (0 paid, 2 pending, 4 expired, 6 cancelled).
The hosted payment page (method 2) is not used: it puts the API key in the
URL shown to every customer.
"""

import os

import httpx

BASE = "https://paygateglobal.com"
NETWORKS = ("FLOOZ", "TMONEY")
PAY_STATUS = {0: "recorded", 2: "invalid_token", 4: "invalid_parameters", 6: "duplicate"}
PAYMENT_STATUS = {0: "paid", 2: "pending", 4: "expired", 6: "cancelled"}


def configured() -> bool:
    return bool(os.getenv("PAYGATE_API_KEY", "").strip())


def _post(path: str, payload: dict) -> dict:
    response = httpx.post(
        f"{BASE}{path}",
        json={"auth_token": os.environ["PAYGATE_API_KEY"].strip(), **payload},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def request_payment(
    phone: str, amount: int, identifier: str, network: str, description: str
) -> dict:
    return _post(
        "/api/v1/pay",
        {
            "phone_number": phone,
            "amount": amount,
            "identifier": identifier,
            "network": network,
            "description": description,
        },
    )


def payment_status(identifier: str) -> dict:
    return _post("/api/v2/status", {"identifier": identifier})
