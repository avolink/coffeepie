"""Tests for the COFP ledger. Pure logic — no FastAPI/Firebase needed.

Run: PYTHONPATH=. python -m unittest tests.test_ledger
"""

import unittest
from decimal import Decimal

from app.cofp.ledger import CofpLedger, LedgerError, effective_rate_cop
from app.cofp.metering import UsageSample


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = CofpLedger()

    def test_accrual_credits_provider(self):
        s = UsageSample("i1", "prov", "user", slices=2, seconds=600, streaming=True)
        minted = self.ledger.accrue_for_usage(s)
        self.assertEqual(minted, Decimal("20"))  # 2 slices * 10 min
        self.assertEqual(self.ledger.balance("prov"), Decimal("20"))
        # The consumer is not credited; only the hosting provider.
        self.assertEqual(self.ledger.balance("user"), Decimal("0"))

    def test_ineffective_usage_writes_no_entry(self):
        s = UsageSample("i1", "prov", "user", slices=4, seconds=600, streaming=False)
        self.assertEqual(self.ledger.accrue_for_usage(s), Decimal("0"))
        self.assertEqual(self.ledger.repo.entries_for("prov"), [])

    def test_voting_power_tracks_balance(self):
        self.ledger.accrue_for_usage(UsageSample("i", "c", "u", 1, 300, True))
        self.assertEqual(self.ledger.voting_power("c"), Decimal("5"))

    def test_spend_requires_balance(self):
        with self.assertRaises(LedgerError):
            self.ledger.spend("broke", Decimal("1"), "campaign")

    def test_spend_decrements(self):
        self.ledger.accrue_for_usage(UsageSample("i", "acct", "u", 1, 600, True))
        self.ledger.spend("acct", Decimal("4"), "campaign settlement")
        self.assertEqual(self.ledger.balance("acct"), Decimal("6"))

    def test_withdraw_burns_and_quotes_fiat(self):
        # 1 slice * 100 min = 100 COFP.
        self.ledger.accrue_for_usage(UsageSample("i", "prov", "u", 1, 6000, True))
        quote = self.ledger.withdraw("prov", Decimal("100"), "tier2")
        # tier2 = 0.29 * 1.10 = 0.319 COP/COFP → 31 COP (floored).
        self.assertEqual(quote.effective_rate_cop, Decimal("0.319"))
        self.assertEqual(quote.payout_cop, 31)
        self.assertEqual(self.ledger.balance("prov"), Decimal("0"))

    def test_withdraw_insufficient_balance(self):
        with self.assertRaises(LedgerError):
            self.ledger.withdraw("prov", Decimal("1"), "tier1")

    def test_tier_margins(self):
        self.assertEqual(effective_rate_cop("tier1"), Decimal("0.29") * Decimal("1.08"))
        self.assertEqual(effective_rate_cop("tier5"), Decimal("0.29") * Decimal("1.18"))


if __name__ == "__main__":
    unittest.main()
