"""Read endpoints for the remaining panel tabs (QA-data-backed).

All scoped to the caller's own rows (admins, e.g. testing@, effectively see
their own seeded data). Generic helper keeps each endpoint a one-liner.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.identity import AuthenticatedUser, Role
from app.auth.rbac import require_roles, verify_bearer_token
from app.db import get_conn

router = APIRouter(prefix="/panel", tags=["panel-data"])


def _query(sql: str, uid: str) -> list[dict]:
    """Run a SELECT scoped to one user, return list of dict rows."""
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, (uid,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            cur.close()
    # Stringify non-JSON-native types (dates, Decimal) for stable transport.
    for row in rows:
        for k, v in list(row.items()):
            if hasattr(v, "isoformat"):
                row[k] = v.isoformat()
            elif type(v).__name__ == "Decimal":
                row[k] = str(v)
    return rows


@router.get("/campaigns")
def campaigns(user: AuthenticatedUser = Depends(require_roles(Role.ADVERTISER))):
    return _query(
        "SELECT name, objective, budget_cop, start_date, segment, status, "
        "impressions, ctr, asset_count FROM campaign WHERE owner_id = %s::uuid "
        "ORDER BY created_at DESC", user.uid)


@router.get("/segments")
def segments(user: AuthenticatedUser = Depends(require_roles(Role.ADVERTISER))):
    return _query(
        "SELECT name, age_min, age_max, industry, role, region, size_estimate "
        "FROM segment WHERE owner_id = %s::uuid ORDER BY created_at DESC", user.uid)


@router.get("/assets")
def assets(user: AuthenticatedUser = Depends(require_roles(Role.ADVERTISER))):
    return _query(
        "SELECT name, category, tags, file_type, size_kb, status "
        "FROM asset WHERE owner_id = %s::uuid ORDER BY created_at DESC", user.uid)


@router.get("/invoices")
def invoices(user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _query(
        "SELECT invoice_number, issued_on, concept, amount_cop, credits, status "
        "FROM invoice WHERE user_id = %s::uuid ORDER BY issued_on DESC", user.uid)


@router.get("/apikeys")
def apikeys(user: AuthenticatedUser = Depends(verify_bearer_token)):
    return _query(
        "SELECT name, masked_key, environment, created_at, last_used "
        "FROM api_key WHERE user_id = %s::uuid ORDER BY created_at DESC", user.uid)


@router.get("/licenses")
def licenses(user: AuthenticatedUser = Depends(require_roles(Role.MANUFACTURER, Role.ADVERTISER))):
    return _query(
        "SELECT license_key, terminals, plan_type, period, start_date, expiration, status "
        "FROM qfdm_license WHERE user_id = %s::uuid ORDER BY created_at DESC", user.uid)


@router.get("/withdrawals")
def withdrawals(user: AuthenticatedUser = Depends(require_roles(Role.PROVIDER, Role.CONTRIBUTOR))):
    return _query(
        "SELECT cofp_burned, cop_received, concept, status, created_at "
        "FROM withdrawal WHERE user_id = %s::uuid ORDER BY created_at DESC", user.uid)
