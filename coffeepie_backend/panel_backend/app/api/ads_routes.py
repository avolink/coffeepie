"""Ad serving + the Cr credit wallet.

The monetization loop: advertisers create campaigns and audience segments in
the panel (Campañas / Segmentación); consumers open the ads window (honey
button) and are served the ad that best fits them; completing the view earns
Cr, debited conceptually from the advertiser's budget.

Selection — "best suited and/or best bid":
  1. every ACTIVE campaign with budget is scored against the viewer's
     audience profile (app_user.audience JSONB) via its segment's criteria:
     age range, role, region, industry-vs-interests;
  2. rank by match score DESC (best suited), tiebreak budget DESC (best bid);
  3. no campaign inventory → a Coffee Pie house ad fills the slot, so the
     reward loop still works.

Endpoints:
  GET  /ads/next          the ad to show now (campaign or house)
  POST /ads/complete      register the impression + credit the reward
  GET  /credits/balance   real Cr Saldo = SUM(credit_ledger.delta_cr)

Honest scope: budget is not yet decremented per impression (needs the
COP→Cr conversion policy) and creatives are text cards (asset files have no
storage/URL yet) — both labelled here rather than faked.
"""
from __future__ import annotations

import json
import uuid as uuidlib

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.identity import AuthenticatedUser
from app.auth.rbac import verify_bearer_token
from app.db import get_conn

router = APIRouter(tags=["ads"])

AD_REWARD_CR = 500
AD_SECONDS = 30          # production ad length; the QA frontend may shorten


class CompleteIn(BaseModel):
    campaign_id: str | None = None


def _audience(uid: str) -> dict:
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT audience FROM app_user WHERE id = %s::uuid", (uid,))
            row = cur.fetchone()
        finally:
            cur.close()
    raw = row[0] if row else None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
    return raw or {}


def _match_score(aud: dict, age_min, age_max, industry, role, region) -> int:
    """How well a segment fits the viewer. Unknown viewer fields simply don't
    score — an empty profile matches every campaign equally (score 0)."""
    score = 0
    age = aud.get("age")
    if age is not None and age_min is not None and age_max is not None:
        if age_min <= int(age) <= age_max:
            score += 2
        else:
            return -1                     # actively outside the target age
    interests = [str(i).lower() for i in (aud.get("interests") or [])]
    if industry and industry.lower() in interests:
        score += 2
    if role and str(aud.get("role", "")).lower() == role.lower():
        score += 1
    if region and str(aud.get("region", "")).lower() == region.lower():
        score += 1
    return score


def _house_ad() -> dict:
    return {
        "campaign_id": None, "house": True,
        "name": "Coffee Pie — La Red QFDM",
        "brand": "Coffee Pie",
        "objective": "Comparte tu cómputo, gana COFP",
        "reward_cr": AD_REWARD_CR, "duration_s": AD_SECONDS, "match_score": 0,
    }


@router.get("/ads/next")
def next_ad(user: AuthenticatedUser = Depends(verify_bearer_token)):
    aud = _audience(user.uid)
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            # campaign.segment is the segment's NAME (panel keeps them per owner)
            cur.execute(
                "SELECT c.id, c.name, c.objective, c.budget_cop, u.display_name, "
                "       s.age_min, s.age_max, s.industry, s.role, s.region "
                "FROM campaign c "
                "JOIN app_user u ON u.id = c.owner_id "
                "LEFT JOIN segment s ON s.owner_id = c.owner_id AND s.name = c.segment "
                "WHERE c.status = 'active' AND c.budget_cop > 0"
            )
            rows = cur.fetchall()
        finally:
            cur.close()

    best, best_key = None, None
    for cid, name, obj, budget, brand, a1, a2, ind, role, reg in rows:
        score = _match_score(aud, a1, a2, ind, role, reg)
        if score < 0:
            continue                      # excluded by targeting
        key = (score, int(budget or 0))   # best suited, then best bid
        if best_key is None or key > best_key:
            best_key = key
            best = {"campaign_id": str(cid), "house": False, "name": name,
                    "brand": brand or "Anunciante", "objective": obj or "",
                    "reward_cr": AD_REWARD_CR, "duration_s": AD_SECONDS,
                    "match_score": score}
    return best or _house_ad()


@router.post("/ads/complete")
def complete_ad(body: CompleteIn, user: AuthenticatedUser = Depends(verify_bearer_token)):
    imp_id = str(uuidlib.uuid4())
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO ad_impression (id, user_id, campaign_id, reward_cr) "
                "VALUES (%s::uuid, %s::uuid, %s::uuid, %s)",
                (imp_id, user.uid, body.campaign_id, AD_REWARD_CR))
            if body.campaign_id:
                cur.execute("UPDATE campaign SET impressions = impressions + 1 "
                            "WHERE id = %s::uuid", (body.campaign_id,))
            cur.execute(
                "INSERT INTO credit_ledger (user_id, delta_cr, reason, ref) "
                "VALUES (%s::uuid, %s, 'ad_reward', %s::uuid)",
                (user.uid, AD_REWARD_CR, imp_id))
            cur.execute("SELECT COALESCE(SUM(delta_cr), 0) FROM credit_ledger "
                        "WHERE user_id = %s::uuid", (user.uid,))
            balance = cur.fetchone()[0]
            conn.commit()
        finally:
            cur.close()
    return {"reward_cr": AD_REWARD_CR, "balance": float(balance)}


@router.get("/credits/balance")
def credit_balance(user: AuthenticatedUser = Depends(verify_bearer_token)):
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT COALESCE(SUM(delta_cr), 0) FROM credit_ledger "
                        "WHERE user_id = %s::uuid", (user.uid,))
            balance = cur.fetchone()[0]
        finally:
            cur.close()
    return {"credits": float(balance)}
