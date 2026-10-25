"""
Paid plans for API keys, paid by mobile money through PayGate Global.

Prices are a business decision, configured in BILLING_PLANS, e.g.
  {"dev": {"label": "Développeur", "monthly_fcfa": 5000}}
(plan names are those of api.app.core.rate_limit). Unset: no checkout.

A payment is only trusted once PayGate's status API says it is paid (status
0) for our identifier and amount: PayGate's callback is not signed, so it
only triggers that check.
"""

import json
import os
import re
import uuid

from api.app.core.rate_limit import PLAN_QUOTAS
from api.app.features.billing import paygate
from db import get_conn

DAYS_PER_MONTH = 30


class BillingError(ValueError):
    pass


def plans() -> dict[str, dict]:
    try:
        configured = json.loads(os.getenv("BILLING_PLANS", "") or "{}")
    except ValueError:
        return {}
    return {
        name: {
            "label": str(conf.get("label") or name),
            "monthly_fcfa": int(conf["monthly_fcfa"]),
            "quota_per_day": PLAN_QUOTAS[name],
        }
        for name, conf in configured.items()
        if name in PLAN_QUOTAS and name not in ("anon", "free") and conf.get("monthly_fcfa")
    }


def normalize_phone(phone: str) -> str:
    """8-digit Togolese number from '+228 90 12 34 56', '22890123456'..."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits.startswith("228"):
        digits = digits[3:]
    if len(digits) != 8:
        raise BillingError("invalid phone number")
    return digits


def checkout(api_key_id: str, plan: str, months: int, phone: str, network: str) -> dict:
    offer = plans().get(plan)
    if not offer or not paygate.configured():
        raise BillingError("plan not available")
    if network not in paygate.NETWORKS or not 1 <= months <= 12:
        raise BillingError("invalid parameters")
    phone = normalize_phone(phone)
    amount = offer["monthly_fcfa"] * months
    identifier = f"TLM-{uuid.uuid4().hex[:16]}"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (identifier, api_key_id, plan, months, amount, network)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (identifier, api_key_id, plan, months, amount, network),
            )
        conn.commit()
        result = paygate.request_payment(
            phone, amount, identifier, network, f"TogoLM {offer['label']} - {months} mois"
        )
        with conn.cursor() as cur:
            if result.get("status") == 0:
                cur.execute(
                    "UPDATE payments SET tx_reference = %s WHERE identifier = %s",
                    (result.get("tx_reference"), identifier),
                )
            else:
                cur.execute(
                    "UPDATE payments SET status = 'failed' WHERE identifier = %s", (identifier,)
                )
        conn.commit()
    finally:
        conn.close()
    if result.get("status") != 0:
        raise BillingError(paygate.PAY_STATUS.get(result.get("status"), "payment refused"))
    return {"identifier": identifier, "amount": amount, "status": "pending"}


def refresh(identifier: str) -> dict | None:
    """Payment row after asking PayGate for its status; activates the plan once paid."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT api_key_id::text, plan, months, amount, status FROM payments "
                "WHERE identifier = %s FOR UPDATE",
                (identifier,),
            )
            row = cur.fetchone()
            if not row:
                return None
            key_id, plan, months, amount, status = row
            if status == "pending":
                remote = paygate.payment_status(identifier)
                new_status = paygate.PAYMENT_STATUS.get(remote.get("status"), "pending")
                if new_status == "paid":
                    cur.execute(
                        """
                        UPDATE payments SET status = 'paid', paid_at = NOW(),
                               payment_reference = %s, payment_method = %s,
                               tx_reference = COALESCE(tx_reference, %s)
                        WHERE identifier = %s
                        """,
                        (
                            remote.get("payment_reference"),
                            remote.get("payment_method"),
                            remote.get("tx_reference"),
                            identifier,
                        ),
                    )
                    # A renewal of the same plan extends it; anything else
                    # starts now.
                    cur.execute(
                        """
                        UPDATE api_keys SET
                            plan_expires_at = CASE
                                WHEN plan = %s AND plan_expires_at > NOW()
                                THEN plan_expires_at ELSE NOW() END + %s * interval '1 day',
                            plan = %s
                        WHERE id = %s
                        """,
                        (plan, months * DAYS_PER_MONTH, plan, key_id),
                    )
                elif new_status in ("expired", "cancelled"):
                    cur.execute(
                        "UPDATE payments SET status = %s WHERE identifier = %s",
                        (new_status, identifier),
                    )
                status = new_status
        conn.commit()
    finally:
        conn.close()
    return {
        "identifier": identifier,
        "plan": plan,
        "months": months,
        "amount": amount,
        "status": status,
        "api_key_id": key_id,
    }
