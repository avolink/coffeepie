-- Coffee Pie Panel — QA test database schema (PostgreSQL).
--
-- Mirrors the panel_backend domain: roles (RBAC), the COFP ledger, and the
-- provider node registry. Designed to port cleanly to Supabase: when running on
-- Supabase, `app_user` maps to `auth.users` and the role/RLS notes below apply.
--
-- Money safety: all COFP amounts are NUMERIC(38,6) (exact Decimal, never float),
-- matching app/cofp/metering.py's micro-COFP quantum.
--
-- Idempotent: safe to re-run.

BEGIN;

-- ── Enums ───────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE cofp_role AS ENUM
        ('advertiser', 'manufacturer', 'provider', 'contributor', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE ledger_entry_type AS ENUM
        ('accrual', 'spend', 'withdrawal', 'transfer_in', 'transfer_out', 'adjustment');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE node_status AS ENUM ('active', 'maintenance', 'offline');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Identity (test-local; on Supabase this is auth.users) ───────────────
CREATE TABLE IF NOT EXISTS app_user (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A user may hold several roles (Provider who also advertises, etc.).
CREATE TABLE IF NOT EXISTS user_role (
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    role    cofp_role NOT NULL,
    PRIMARY KEY (user_id, role)
);

-- ── COFP ledger (append-only source of truth) ──────────────────────────
-- Balance is DERIVED from entries (see account_balance view), never stored,
-- so it can never drift from the journal.
CREATE TABLE IF NOT EXISTS ledger_entry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      TEXT NOT NULL,                 -- user uid (text: matches IdP sub)
    entry_type      ledger_entry_type NOT NULL,
    amount          NUMERIC(38,6) NOT NULL,        -- signed: + credit, - debit
    reason          TEXT NOT NULL DEFAULT '',
    instance_id     TEXT,                          -- provenance for accruals
    -- Idempotency key for metering ingest: a single (instance, window) may only
    -- accrue once, so DC-Agent retries can NEVER double-mint. NULL for entries
    -- that are not dedup-guarded (spends, manual adjustments). A plain UNIQUE is
    -- used deliberately: Postgres treats NULLs as distinct, so unlimited NULL
    -- rows are allowed while every non-null key is enforced unique. (A partial
    -- index would not work with ON CONFLICT inference.)
    dedup_key       TEXT UNIQUE,
    settled_onchain BOOLEAN NOT NULL DEFAULT FALSE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ledger_account ON ledger_entry (account_id);
CREATE INDEX IF NOT EXISTS ix_ledger_type    ON ledger_entry (entry_type);
CREATE INDEX IF NOT EXISTS ix_ledger_ts      ON ledger_entry (ts);

-- Derived balance per account.
CREATE OR REPLACE VIEW account_balance AS
    SELECT account_id, COALESCE(SUM(amount), 0)::NUMERIC(38,6) AS balance
    FROM ledger_entry
    GROUP BY account_id;

-- ── Provider node registry (the "Registrar Nodo" form) ─────────────────
CREATE TABLE IF NOT EXISTS node (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    public_ip   INET,
    vcores      INTEGER NOT NULL CHECK (vcores      >= 0),
    ram_gb      INTEGER NOT NULL CHECK (ram_gb      >= 0),
    ssd_gb      INTEGER NOT NULL CHECK (ssd_gb      >= 0),
    gpu_vram_mb INTEGER NOT NULL DEFAULT 0 CHECK (gpu_vram_mb >= 0),
    hypervisor  TEXT NOT NULL DEFAULT 'proxmox',
    location    TEXT,
    status      node_status NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_node_provider ON node (provider_id);

COMMIT;

-- ── Row-Level Security (apply on Supabase) ─────────────────────────────
-- Left as documentation rather than active policies, because on this test-local
-- Postgres there is no auth.uid(). On Supabase, enable and adapt:
--
--   ALTER TABLE ledger_entry ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY own_entries ON ledger_entry
--     FOR SELECT USING (account_id = auth.uid()::text);
--   ALTER TABLE node ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY own_nodes ON node
--     FOR ALL USING (provider_id = auth.uid());
--
-- IMPORTANT: the service-role key bypasses RLS. The /cofp/usage ingest and the
-- settlement worker run as service-role, so they MUST keep ownership checks in
-- application code — RLS does not protect those paths.
