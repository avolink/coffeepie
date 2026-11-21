-- ── 0006: stop the balance view from bypassing row-level security ──────────
-- Every table in this schema has RLS on, but a plain VIEW runs with the
-- privileges of its owner (postgres), which is exempt from RLS. Exposed through
-- Supabase's API, account_balance would therefore return EVERY account's COFP
-- balance to any caller. security_invoker makes the view run as the caller, so
-- the own_entries policy on ledger_entry applies to it as well (Postgres 15+,
-- which Supabase uses).
ALTER VIEW account_balance SET (security_invoker = true);

-- Belt and braces: the anonymous role has no business reading balances at all.
REVOKE ALL ON account_balance FROM anon;
