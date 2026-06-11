"""COFP panel endpoints — accrual ingest, balances, governance, withdrawal.

These back the Proveedores tab (earnings/withdraw), the Contributor voting view,
and any balance widgets. Each route is role-gated via require_roles.

The shared ledger instance here uses the in-memory repository, so balances reset
on restart — fine for dev. Wiring a durable LedgerRepository (Postgres) is the
first thing the partner does; see README.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException

from app.auth.identity import AuthenticatedUser
from app.auth.rbac import Role, require_roles, verify_bearer_token
from app.cofp.ledger import CofpLedger, EntryType, LedgerError
from app.cofp.metering import UsageSample
from app.models.panel_models import (
    AccrualOut,
    BalanceOut,
    ProviderSummaryOut,
    UsageEventIn,
    WithdrawIn,
    WithdrawOut,
)

router = APIRouter(prefix="/cofp", tags=["cofp"])


def _make_ledger() -> CofpLedger:
    """Select the ledger repository by env. LEDGER_BACKEND=postgres uses the
    durable DB-backed repo; anything else (default) uses in-memory for dev."""
    import os

    if os.getenv("LEDGER_BACKEND", "memory").lower() == "postgres":
        from app.cofp.pg_repository import PostgresLedgerRepository

        return CofpLedger(PostgresLedgerRepository())
    return CofpLedger()


_ledger = _make_ledger()


def _uid(user: AuthenticatedUser) -> str:
    if not user.uid:
        raise HTTPException(status_code=401, detail="Token missing uid")
    return user.uid


@router.post("/usage", response_model=AccrualOut)
def ingest_usage(
    event: UsageEventIn,
    _token: AuthenticatedUser = Depends(require_roles(Role.ADMIN)),
):
    """Metering ingest from the DC Agent (service-authenticated as ADMIN).

    Accrues COFP to the hosting Provider for one effectively-served window.
    Idempotency across retries is the caller's responsibility for now — see
    README (a dedup key on (instance_id, window) belongs in the DB layer).
    """
    sample = UsageSample(
        instance_id=event.instance_id,
        provider_id=event.provider_id,
        user_id=event.user_id,
        slices=event.slices,
        seconds=event.seconds,
        streaming=event.streaming,
    )
    minted = _ledger.accrue_for_usage(sample)
    return AccrualOut(
        instance_id=event.instance_id,
        cofp_minted=str(minted),
        provider_balance=str(_ledger.balance(event.provider_id)),
    )


@router.get("/balance", response_model=BalanceOut)
def get_balance(token: AuthenticatedUser = Depends(verify_bearer_token)):
    """Caller's own COFP balance and voting power. Any authenticated user."""
    uid = _uid(token)
    return BalanceOut(
        account_id=uid,
        cofp_balance=str(_ledger.balance(uid)),
        voting_power=str(_ledger.voting_power(uid)),
    )


@router.get("/provider/summary", response_model=ProviderSummaryOut)
def provider_summary(token: AuthenticatedUser = Depends(require_roles(Role.PROVIDER))):
    """Backs the Proveedores tab headline numbers (tokens this month, etc.)."""
    uid = _uid(token)
    entries = _ledger.repo.entries_for(uid)
    now = datetime.now(timezone.utc)
    month_total = Decimal(0)
    served = 0
    for e in entries:
        if e.entry_type is EntryType.ACCRUAL:
            served += 1
            ts = datetime.fromisoformat(e.ts)
            if ts.year == now.year and ts.month == now.month:
                month_total += e.amount
    return ProviderSummaryOut(
        account_id=uid,
        cofp_balance=str(_ledger.balance(uid)),
        cofp_this_month=str(month_total),
        served_instances=served,
    )


@router.get("/governance/voting-power", response_model=BalanceOut)
def voting_power(token: AuthenticatedUser = Depends(require_roles(Role.CONTRIBUTOR))):
    """Contributor voting weight on technical decisions."""
    uid = _uid(token)
    return BalanceOut(
        account_id=uid,
        cofp_balance=str(_ledger.balance(uid)),
        voting_power=str(_ledger.voting_power(uid)),
    )


@router.post("/withdraw", response_model=WithdrawOut)
def withdraw(
    body: WithdrawIn,
    token: AuthenticatedUser = Depends(require_roles(Role.PROVIDER, Role.CONTRIBUTOR)),
):
    """Burn COFP for fiat. Writes the burn to the ledger and returns a quote.

    Bank payout and the on-chain burnFrom are NOT performed here — a settlement
    worker (partner) consumes the WITHDRAWAL entry and executes both. This split
    keeps the irreversible money/chain actions out of the request path.
    """
    uid = _uid(token)
    try:
        amount = Decimal(body.cofp_amount)
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=400, detail="cofp_amount is not a valid decimal")
    try:
        quote = _ledger.withdraw(uid, amount, body.tier)
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return WithdrawOut(
        cofp_burned=str(quote.cofp_burned),
        tier=quote.tier,
        effective_rate_cop=str(quote.effective_rate_cop),
        payout_cop=quote.payout_cop,
        ledger_entry_id=quote.entry_id,
        note="Burn recorded. Bank payout + on-chain burnFrom pending settlement worker.",
    )
