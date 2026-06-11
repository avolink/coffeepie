"""COFP ledger — off-chain source of truth for token accrual and burn.

Responsibilities:
  * accrue COFP to Providers as their nodes effectively serve slices (metering),
  * report balances and Contributor voting power,
  * burn COFP on withdrawal and quote the fiat payout (tier-adjusted).

Design notes:
  * This ledger is the authoritative off-chain record. On-chain mint/burn on the
    COFP_Token contract is a *settlement* step layered on top — the chain should
    mirror this ledger, not race it. The signer/settlement worker is partner work
    (see README); `LedgerEntry.settled_onchain` tracks that hand-off.
  * Storage is behind `LedgerRepository` (a Protocol). The in-memory impl here is
    for tests/dev; the partner swaps in Postgres without touching this logic.
  * Money is Decimal, quantized to the micro-COFP. No floats, ever.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Protocol
import uuid

from app.cofp.metering import UsageSample, cofp_for_sample, COFP_QUANTUM


class EntryType(str, Enum):
    ACCRUAL = "accrual"      # +COFP minted to a Provider for serving slices
    SPEND = "spend"          # -COFP spent (e.g. Advertiser/consumer settlement)
    WITHDRAWAL = "withdrawal"  # -COFP burned in exchange for fiat
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT = "adjustment"  # manual correction (audited)


@dataclass(frozen=True)
class LedgerEntry:
    account_id: str
    entry_type: EntryType
    amount: Decimal           # signed: + increases balance, - decreases
    reason: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    instance_id: str | None = None   # provenance for accruals
    settled_onchain: bool = False     # has the chain mirrored this yet?
    dedup_key: str | None = None      # idempotency guard (DB UNIQUE) for accruals


class LedgerError(Exception):
    """Raised on an invalid ledger operation (e.g. insufficient balance)."""


# Tier liquidation margins, mirroring panel.html TIER_RATES. Providers in higher
# datacenter tiers get a better fiat conversion when they burn COFP.
COFP_BASE_COP = Decimal("0.29")  # governance-voted global base; see /api/pricing
TIER_MARGINS: dict[str, Decimal] = {
    "tier1": Decimal("0.08"),
    "tier2": Decimal("0.10"),
    "tier3": Decimal("0.12"),
    "tier4": Decimal("0.15"),
    "tier5": Decimal("0.18"),
}


def effective_rate_cop(tier: str) -> Decimal:
    """Effective COP paid per COFP burned, for a given datacenter tier."""
    margin = TIER_MARGINS.get(tier, TIER_MARGINS["tier1"])
    return COFP_BASE_COP * (Decimal(1) + margin)


class LedgerRepository(Protocol):
    """Persistence boundary. Swap the in-memory impl for a real DB in prod."""

    def append(self, entry: LedgerEntry) -> None: ...
    def entries_for(self, account_id: str) -> list[LedgerEntry]: ...
    def balance_of(self, account_id: str) -> Decimal: ...


class InMemoryLedgerRepository:
    """Dev/test repository. Not durable, not concurrency-safe across processes."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []
        self._balances: dict[str, Decimal] = {}

    def append(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)
        self._balances[entry.account_id] = (
            self._balances.get(entry.account_id, Decimal(0)) + entry.amount
        )

    def entries_for(self, account_id: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.account_id == account_id]

    def balance_of(self, account_id: str) -> Decimal:
        return self._balances.get(account_id, Decimal(0))


@dataclass(frozen=True)
class PayoutQuote:
    """Result of a withdrawal: COFP burned and the fiat the user will receive."""
    cofp_burned: Decimal
    tier: str
    effective_rate_cop: Decimal
    payout_cop: int           # floored to whole COP
    entry_id: str


class CofpLedger:
    """Application service over a LedgerRepository."""

    def __init__(self, repo: LedgerRepository | None = None) -> None:
        self.repo = repo if repo is not None else InMemoryLedgerRepository()

    # ── Accrual (Providers earn) ─────────────────────────────────────────
    def accrue_for_usage(self, sample: UsageSample) -> Decimal:
        """Mint COFP to the hosting Provider for one effectively-served sample.

        Returns the COFP minted (0 if the sample was not effectively served, in
        which case no entry is written).
        """
        amount = cofp_for_sample(sample)
        if amount <= 0:
            return Decimal(0)
        self.repo.append(LedgerEntry(
            account_id=sample.provider_id,
            entry_type=EntryType.ACCRUAL,
            amount=amount,
            reason="slice-minutes effectively served",
            instance_id=sample.instance_id,
        ))
        return amount

    # ── Balances & governance ────────────────────────────────────────────
    def balance(self, account_id: str) -> Decimal:
        return self.repo.balance_of(account_id)

    def voting_power(self, account_id: str) -> Decimal:
        """Contributor voting weight on technical decisions.

        1 COFP held = 1 vote. Kept as its own method so governance can later
        switch to staked/time-locked weighting without touching call sites.
        """
        return max(Decimal(0), self.repo.balance_of(account_id))

    # ── Spend (Advertisers/consumers settle) ─────────────────────────────
    def spend(self, account_id: str, amount: Decimal, reason: str) -> LedgerEntry:
        amount = amount.quantize(COFP_QUANTUM)
        if amount <= 0:
            raise LedgerError("spend amount must be positive")
        if self.repo.balance_of(account_id) < amount:
            raise LedgerError("insufficient COFP balance")
        entry = LedgerEntry(
            account_id=account_id,
            entry_type=EntryType.SPEND,
            amount=-amount,
            reason=reason,
        )
        self.repo.append(entry)
        return entry

    # ── Withdrawal (burn COFP → fiat) ────────────────────────────────────
    def withdraw(self, account_id: str, amount: Decimal, tier: str) -> PayoutQuote:
        """Burn COFP from `account_id` and quote the fiat payout.

        This writes the burn to the ledger and returns a quote. It does NOT move
        money or touch the chain — that is the settlement worker's job (initiate
        bank payout via payments backend; call burnFrom on COFP_Token). Both are
        partner integrations; see README.
        """
        amount = amount.quantize(COFP_QUANTUM)
        if amount <= 0:
            raise LedgerError("withdrawal amount must be positive")
        if self.repo.balance_of(account_id) < amount:
            raise LedgerError("insufficient COFP balance")

        rate = effective_rate_cop(tier)
        payout_cop = int((amount * rate).to_integral_value(rounding="ROUND_DOWN"))

        entry = LedgerEntry(
            account_id=account_id,
            entry_type=EntryType.WITHDRAWAL,
            amount=-amount,
            reason=f"burn→fiat @ {rate} COP/COFP ({tier})",
        )
        self.repo.append(entry)
        return PayoutQuote(
            cofp_burned=amount,
            tier=tier,
            effective_rate_cop=rate,
            payout_cop=payout_cop,
            entry_id=entry.id,
        )
