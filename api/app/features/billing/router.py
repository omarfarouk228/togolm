"""
GET  /v1/billing/plans                  — Paid plans and prices (public)
POST /v1/billing/checkout               — Pay a plan by mobile money (X-API-Key)
GET  /v1/billing/payments/{identifier}  — Payment status, activates the plan once paid
POST /v1/billing/paygate/callback       — PayGate's confirmation (set as return URL in PayGate)
GET  /v1/admin/billing/plans, PUT /v1/admin/billing/plans/{plan}, GET /v1/admin/billing/payments
                                        — prices and payments, for the admin
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.app.core.auth import APIKeyRecord, get_api_key
from api.app.features.admin.service import require_admin
from api.app.features.billing import paygate, service

logger = logging.getLogger("togolm.billing")
router = APIRouter(tags=["Billing"])


class CheckoutRequest(BaseModel):
    plan: str = Field(..., max_length=20)
    months: int = Field(1, ge=1, le=12)
    phone: str = Field(..., max_length=20)
    network: str = Field(..., description="FLOOZ or TMONEY")


class PlanUpdate(BaseModel):
    label: str = Field(..., min_length=2, max_length=60)
    monthly_fcfa: int | None = Field(None, gt=0, le=10_000_000)
    active: bool = False


def _key(api_key: APIKeyRecord | str | None) -> APIKeyRecord:
    if not isinstance(api_key, APIKeyRecord):
        raise HTTPException(status_code=401, detail="A registered X-API-Key is required")
    return api_key


@router.get("/billing/plans")
def billing_plans():
    return {
        "available": paygate.configured(),
        "plans": service.plans(),
        "networks": paygate.NETWORKS,
    }


@router.post("/billing/checkout", status_code=202)
def checkout(body: CheckoutRequest, api_key: APIKeyRecord | str | None = Depends(get_api_key)):
    key = _key(api_key)
    try:
        payment = service.checkout(key.id, body.plan, body.months, body.phone, body.network.upper())
    except service.BillingError as e:
        status = 503 if str(e) == "plan not available" else 422
        raise HTTPException(status_code=status, detail=str(e)) from None
    return {**payment, "message": "Validez le paiement sur votre téléphone."}


@router.get("/billing/payments")
def my_payments(api_key: APIKeyRecord | str | None = Depends(get_api_key)):
    """This key's payments, newest first (developer console)."""
    key = _key(api_key)
    hidden = ("owner_name", "owner_email")
    return {
        "items": [
            {k: v for k, v in p.items() if k not in hidden}
            for p in service.recent_payments(50, api_key_id=key.id)
        ]
    }


@router.get("/billing/payments/{identifier}")
def payment(identifier: str, api_key: APIKeyRecord | str | None = Depends(get_api_key)):
    key = _key(api_key)
    result = service.refresh(identifier)
    if not result or result["api_key_id"] != key.id:
        raise HTTPException(status_code=404, detail="Payment not found")
    return {k: v for k, v in result.items() if k != "api_key_id"}


@router.post("/billing/paygate/callback", include_in_schema=False)
async def paygate_callback(request: Request):
    """Not signed by PayGate: only triggers a status check through PayGate's API."""
    try:
        identifier = str((await request.json()).get("identifier", ""))[:40]
    except Exception:
        identifier = ""
    if identifier:
        try:
            service.refresh(identifier)
        except Exception:
            logger.exception("PayGate callback check failed for %s", identifier)
    return {"ok": True}


# ── Admin ────────────────────────────────────────────────────────────────────


@router.get("/admin/billing/plans")
def admin_plans(
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    require_admin(authorization, x_admin_key)
    return {"paygate_configured": paygate.configured(), "plans": service.all_plans()}


@router.put("/admin/billing/plans/{plan}")
def admin_update_plan(
    plan: str,
    body: PlanUpdate,
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    require_admin(authorization, x_admin_key)
    try:
        return service.update_plan(plan, body.label, body.monthly_fcfa, body.active)
    except service.BillingError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


@router.get("/admin/billing/payments")
def admin_payments(
    limit: int = Query(100, ge=1, le=500),
    authorization: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    require_admin(authorization, x_admin_key)
    return {"payments": service.recent_payments(limit)}
