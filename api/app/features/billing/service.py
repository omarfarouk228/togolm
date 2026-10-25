"""
Paid plans for API keys, paid by mobile money through PayGate Global.

Prices are a business decision, edited from the admin (billing_plans table,
migration 011): a plan is for sale once it has a price and is switched on.

A payment is only trusted once PayGate's status API says it is paid (status
0) for our identifier and amount: PayGate's callback is not signed, so it
only triggers that check.
"""

import re
import uuid

from api.app.core.rate_limit import PLAN_QUOTAS
from api.app.features.billing import paygate
from db import get_conn

DAYS_PER_MONTH = 30


class BillingError(ValueError):
    pass


def all_plans() -> list[dict]:
    """Every paid plan as edited in the admin, for sale or not."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT plan, label, monthly_fcfa, active, updated_at FROM billing_plans ORDER BY plan"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "plan": plan,
            "label": label,
            "monthly_fcfa": price,
            "active": active,
            "quota_per_day": PLAN_QUOTAS.get(plan),
            "updated_at": updated.isoformat(timespec="minutes") if updated else None,
        }
        for plan, label, price, active, updated in rows
        if plan in PLAN_QUOTAS
    ]


def plans() -> dict[str, dict]:
    """Plans for sale: switched on and priced."""
    return {
        p["plan"]: {k: p[k] for k in ("label", "monthly_fcfa", "quota_per_day")}
        for p in all_plans()
        if p["active"] and p["monthly_fcfa"]
    }


def update_plan(plan: str, label: str, monthly_fcfa: int | None, active: bool) -> dict:
    if plan not in PLAN_QUOTAS or plan in ("anon", "free"):
        raise BillingError("unknown plan")
    if active and not monthly_fcfa:
        raise BillingError("a plan for sale needs a price")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO billing_plans (plan, label, monthly_fcfa, active, updated_at)
                VALUES (%s, %s, %s, %s, NOW())
                ON CONFLICT (plan) DO UPDATE SET label = EXCLUDED.label,
                    monthly_fcfa = EXCLUDED.monthly_fcfa, active = EXCLUDED.active,
                    updated_at = NOW()
                """,
                (plan, label, monthly_fcfa, active),
            )
        conn.commit()
    finally:
        conn.close()
    return next(p for p in all_plans() if p["plan"] == plan)


def recent_payments(limit: int = 100) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.identifier, p.plan, p.months, p.amount, p.network, p.status,
                       p.payment_method, p.created_at, p.paid_at, k.owner_name, k.owner_email
                FROM payments p JOIN api_keys k ON k.id = p.api_key_id
                ORDER BY p.created_at DESC LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    keys = ("identifier", "plan", "months", "amount", "network", "status", "payment_method",
            "created_at", "paid_at", "owner_name", "owner_email")  # fmt: skip
    return [
        {
            k: (v.isoformat(timespec="minutes") if hasattr(v, "isoformat") else v)
            for k, v in zip(keys, r)
        }
        for r in rows
    ]


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
