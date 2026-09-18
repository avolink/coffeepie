"""Postgres-backed LedgerRepository — the durable COFP source of truth.

Implements the same 3-method interface as InMemoryLedgerRepository, against the
ledger_entry table / account_balance view (db/01_schema.sql). Uses the shared
DB-API connection (psycopg in prod, pg8000 in QA), with explicit enum/uuid casts
so both drivers behave identically.

Balance is read from the account_balance VIEW (SUM over entries), never stored,
so it can't drift from the journal.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.cofp.ledger import EntryType, LedgerEntry
from app.db import get_conn


class PostgresLedgerRepository:
    """Durable ledger. Append-only; balance derived from the journal."""

    def append(self, entry: LedgerEntry) -> None:
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO ledger_entry
                        (id, account_id, entry_type, amount, reason,
                         instance_id, dedup_key, settled_onchain, ts)
                    VALUES
                        (%s::uuid, %s, %s::ledger_entry_type, %s, %s,
                         %s, %s, %s, %s::timestamptz)
                    ON CONFLICT (dedup_key) DO NOTHING
                    """,
                    (
                        entry.id,
                        entry.account_id,
                        entry.entry_type.value,
                        entry.amount,
                        entry.reason,
                        entry.instance_id,
                        entry.dedup_key,
                        entry.settled_onchain,
                        entry.ts,
                    ),
                )
                conn.commit()
            finally:
                cur.close()

    def balance_of(self, account_id: str) -> Decimal:
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT balance FROM account_balance WHERE account_id = %s",
                    (account_id,),
                )
                row = cur.fetchone()
            finally:
                cur.close()
        return Decimal(row[0]) if row and row[0] is not None else Decimal(0)

    def entries_for(self, account_id: str) -> list[LedgerEntry]:
        with get_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    SELECT id::text, account_id, entry_type, amount, reason,
                           instance_id, dedup_key, settled_onchain, ts
                    FROM ledger_entry
                    WHERE account_id = %s
                    ORDER BY ts
                    """,
                    (account_id,),
                )
                rows = cur.fetchall()
            finally:
                cur.close()
        return [
            LedgerEntry(
                id=r[0],
                account_id=r[1],
                entry_type=EntryType(r[2]),
                amount=Decimal(r[3]),
                reason=r[4],
                instance_id=r[5],
                dedup_key=r[6],
                settled_onchain=r[7],
                ts=r[8].isoformat() if isinstance(r[8], datetime) else str(r[8]),
            )
            for r in rows
        ]
