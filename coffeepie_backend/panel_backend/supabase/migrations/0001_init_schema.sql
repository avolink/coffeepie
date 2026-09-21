-- Coffee Pie Panel — Supabase (shared/production) schema.
--
-- Companion to db/01_schema.sql + db/05_qa_tabs_data.sql's table shapes,
-- adapted for a REAL Supabase Auth project instead of the local QA Postgres:
--
--   * app_user MIRRORS auth.users (same id, kept in sync by a trigger)
--     instead of minting its own UUIDs — every real signup gets a row here
--     automatically, so user_role/node/ledger_entry/etc. keep working with
--     no code changes.
--   * RLS is turned ON for real (the QA-local Postgres has no auth.uid(), so
--     01_schema.sql only documents these policies as comments — here they run).
--   * NO qa_credential table, NO testing@coffeepie.co, NO demo seed rows —
--     this database holds (or will hold) real users. db/03_qa_auth.sql's own
--     warning applies: those QA-only files must NEVER be applied here.
--
-- Apply once via the project's direct Postgres connection (Project Settings →
-- Database → Connection string):
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/migrations/0001_init_schema.sql
-- Idempotent: safe to re-run (e.g. after adding a later migration file).

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

DO $$ BEGIN
    CREATE TYPE campaign_status AS ENUM ('active', 'paused', 'finished', 'draft');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE invoice_status AS ENUM ('paid', 'pending', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE license_status AS ENUM ('active', 'expired', 'suspended');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Identity: mirrors auth.users, does not replace it ──────────────────
CREATE TABLE IF NOT EXISTS app_user (
    id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email        TEXT UNIQUE NOT NULL,
    display_name TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-provision app_user whenever Supabase Auth creates a user, so the rest
-- of the schema never has to special-case "first login". SECURITY DEFINER:
-- auth.users triggers need elevated privilege to write into public.app_user.
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    INSERT INTO public.app_user (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(
            NEW.raw_user_meta_data ->> 'display_name',
            NEW.raw_user_meta_data ->> 'full_name',
            split_part(NEW.email, '@', 1)
        )
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();

-- A user may hold several roles (Provider who also advertises, etc.). No
-- default role is granted here — role assignment is a separate app decision.
CREATE TABLE IF NOT EXISTS user_role (
    user_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    role    cofp_role NOT NULL,
    PRIMARY KEY (user_id, role)
);

-- ── COFP ledger (append-only source of truth) ──────────────────────────
CREATE TABLE IF NOT EXISTS ledger_entry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      TEXT NOT NULL,
    entry_type      ledger_entry_type NOT NULL,
    amount          NUMERIC(38,6) NOT NULL,
    reason          TEXT NOT NULL DEFAULT '',
    instance_id     TEXT,
    dedup_key       TEXT UNIQUE,
    settled_onchain BOOLEAN NOT NULL DEFAULT FALSE,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ledger_account ON ledger_entry (account_id);
CREATE INDEX IF NOT EXISTS ix_ledger_type    ON ledger_entry (entry_type);
CREATE INDEX IF NOT EXISTS ix_ledger_ts      ON ledger_entry (ts);

CREATE OR REPLACE VIEW account_balance AS
    SELECT account_id, COALESCE(SUM(amount), 0)::NUMERIC(38,6) AS balance
    FROM ledger_entry
    GROUP BY account_id;

-- ── Provider node registry (the "Registrar Nodo" form) ─────────────────
CREATE TABLE IF NOT EXISTS node (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id       UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    public_ip         INET,
    vcores            INTEGER NOT NULL CHECK (vcores      >= 0),
    ram_gb            INTEGER NOT NULL CHECK (ram_gb      >= 0),
    ssd_gb            INTEGER NOT NULL CHECK (ssd_gb      >= 0),
    gpu_vram_mb       INTEGER NOT NULL DEFAULT 0 CHECK (gpu_vram_mb >= 0),
    hypervisor        TEXT NOT NULL DEFAULT 'proxmox',
    location          TEXT,
    status            node_status NOT NULL DEFAULT 'active',
    -- Root credentials so the Orchestrator/Broker can take control of the
    -- node. root_password_enc is Fernet ciphertext — see
    -- app/auth/node_credentials.py. NODE_CRED_ENC_KEY must be a real secret
    -- here, never the QA default.
    root_username     TEXT,
    root_password_enc TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_node_provider ON node (provider_id);

-- A provider can't register two nodes with the same name. Deliberately NO
-- uniqueness on public_ip: several domestic nodes behind one NAT/CGNAT router
-- legitimately share a public IP — the frontend warns about same-IP instead.
CREATE UNIQUE INDEX IF NOT EXISTS ux_node_provider_name ON node (provider_id, name);

-- ── Remaining panel tabs: campaigns, segments, assets, invoices, API keys,
--    QFDM licenses, withdrawals. Schema only — no demo/seed rows here. ────
CREATE TABLE IF NOT EXISTS campaign (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    objective   TEXT,
    budget_cop  BIGINT NOT NULL DEFAULT 0,
    start_date  DATE,
    segment     TEXT,
    status      campaign_status NOT NULL DEFAULT 'active',
    impressions BIGINT NOT NULL DEFAULT 0,
    ctr         NUMERIC(5,2) NOT NULL DEFAULT 0,
    asset_count INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS segment (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    age_min       INTEGER,
    age_max       INTEGER,
    industry      TEXT,
    role          TEXT,
    region        TEXT,
    size_estimate INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS asset (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id   UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    category   TEXT,
    tags       TEXT,
    file_type  TEXT,
    size_kb    INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'ready',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoice (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    issued_on      DATE NOT NULL,
    concept        TEXT NOT NULL,
    amount_cop     BIGINT NOT NULL DEFAULT 0,
    credits        BIGINT NOT NULL DEFAULT 0,
    status         invoice_status NOT NULL DEFAULT 'paid',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_key (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    masked_key  TEXT NOT NULL,   -- e.g. cp_live_••••4f2a — never the real key
    environment TEXT NOT NULL DEFAULT 'production',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS qfdm_license (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    license_key TEXT NOT NULL,
    terminals   INTEGER NOT NULL DEFAULT 1,
    plan_type   TEXT NOT NULL DEFAULT 'Estandar',
    period      TEXT NOT NULL DEFAULT 'Mensual',
    start_date  DATE,
    expiration  DATE,
    status      license_status NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS withdrawal (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    cofp_burned     NUMERIC(38,6) NOT NULL,
    cop_received    BIGINT NOT NULL,
    concept         TEXT,
    status          invoice_status NOT NULL DEFAULT 'paid',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Provenance: the ledger_entry burn this request projects. No FK —
    -- ledger and history may live in different stores.
    ledger_entry_id UUID
);

COMMIT;

-- ── Row-Level Security ──────────────────────────────────────────────────
-- Live here (unlike the QA-local Postgres, which has no auth.uid()). This is
-- defense-in-depth: panel_backend connects with a full Postgres role and does
-- its own ownership checks in application code (see nodes_routes.py etc.),
-- which bypasses RLS just like Supabase's service-role key would. RLS matters
-- if anything ever queries these tables directly via PostgREST/anon key.
BEGIN;

ALTER TABLE app_user ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_profile ON app_user;
CREATE POLICY own_profile ON app_user FOR SELECT USING (id = auth.uid());

ALTER TABLE user_role ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_roles ON user_role;
CREATE POLICY own_roles ON user_role FOR SELECT USING (user_id = auth.uid());

ALTER TABLE ledger_entry ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_entries ON ledger_entry;
CREATE POLICY own_entries ON ledger_entry FOR SELECT USING (account_id = auth.uid()::text);

ALTER TABLE node ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_nodes ON node;
CREATE POLICY own_nodes ON node FOR ALL USING (provider_id = auth.uid());

ALTER TABLE campaign ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_campaigns ON campaign;
CREATE POLICY own_campaigns ON campaign FOR ALL USING (owner_id = auth.uid());

ALTER TABLE segment ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_segments ON segment;
CREATE POLICY own_segments ON segment FOR ALL USING (owner_id = auth.uid());

ALTER TABLE asset ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_assets ON asset;
CREATE POLICY own_assets ON asset FOR ALL USING (owner_id = auth.uid());

ALTER TABLE invoice ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_invoices ON invoice;
CREATE POLICY own_invoices ON invoice FOR ALL USING (user_id = auth.uid());

ALTER TABLE api_key ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_api_keys ON api_key;
CREATE POLICY own_api_keys ON api_key FOR ALL USING (user_id = auth.uid());

ALTER TABLE qfdm_license ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_licenses ON qfdm_license;
CREATE POLICY own_licenses ON qfdm_license FOR ALL USING (user_id = auth.uid());

ALTER TABLE withdrawal ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_withdrawals ON withdrawal;
CREATE POLICY own_withdrawals ON withdrawal FOR ALL USING (user_id = auth.uid());

COMMIT;
