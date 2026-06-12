-- Coffee Pie Panel — QA data for the REMAINING tabs.
--
-- Adds tables + realistic seed for: campaigns, segments, assets, invoices,
-- API keys, QFDM licenses, withdrawals. Tied to the QA users so the panel
-- behaves like real user data for QA inspection.
--
-- The memorable QA user testing@coffeepie.co (uid …ff) is made a full superuser
-- (all roles) and owns data in every tab. ⚠️ QA ONLY. Idempotent.

BEGIN;

-- testing@ sees every tab → give it every role.
INSERT INTO user_role (user_id, role) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'advertiser'),
    ('00000000-0000-0000-0000-0000000000ff', 'manufacturer')
ON CONFLICT DO NOTHING;

-- ── Enums ───────────────────────────────────────────────────────────────
DO $$ BEGIN CREATE TYPE campaign_status AS ENUM ('active','paused','finished','draft');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE invoice_status AS ENUM ('paid','pending','rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE license_status AS ENUM ('active','expired','suspended');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Tables ──────────────────────────────────────────────────────────────
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
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    age_min     INTEGER, age_max INTEGER,
    industry    TEXT, role TEXT, region TEXT,
    size_estimate INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS asset (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    category    TEXT, tags TEXT, file_type TEXT,
    size_kb     INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'ready',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS invoice (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    invoice_number TEXT NOT NULL,
    issued_on   DATE NOT NULL,
    concept     TEXT NOT NULL,
    amount_cop  BIGINT NOT NULL DEFAULT 0,
    credits     BIGINT NOT NULL DEFAULT 0,
    status      invoice_status NOT NULL DEFAULT 'paid',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_key (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    masked_key  TEXT NOT NULL,        -- e.g. cp_live_••••4f2a (never the real key)
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
    start_date  DATE, expiration DATE,
    status      license_status NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS withdrawal (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    cofp_burned NUMERIC(38,6) NOT NULL,
    cop_received BIGINT NOT NULL,
    concept     TEXT,
    status      invoice_status NOT NULL DEFAULT 'paid',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Provenance: the ledger_entry burn this request projects. The settlement
    -- worker joins on it to execute payout + on-chain burnFrom, then flips
    -- status pending → paid. No FK: ledger and history may live in different
    -- stores (in-memory dev ledger writes no ledger_entry row).
    ledger_entry_id UUID
);
ALTER TABLE withdrawal ADD COLUMN IF NOT EXISTS ledger_entry_id UUID;

-- ── Seed (idempotent via fixed UUIDs) ───────────────────────────────────
\set ff '''00000000-0000-0000-0000-0000000000ff'''

-- Campaigns
INSERT INTO campaign (id, owner_id, name, objective, budget_cop, start_date, segment, status, impressions, ctr, asset_count) VALUES
 ('00000000-0000-0000-0000-00000000c001', :ff, 'Lanzamiento Q2 - Terminal Pro', 'awareness', 12000000, '2026-04-01', 'Empresas Tecnológicas', 'active',   12400, 3.80, 4),
 ('00000000-0000-0000-0000-00000000c002', :ff, 'Back to School 2026',          'traffic',    8500000, '2026-03-15', 'Educación',            'active',    8700, 2.10, 7),
 ('00000000-0000-0000-0000-00000000c003', :ff, 'Tech Summit Sponsorship',      'engagement', 5000000, '2026-02-20', 'CTOs LATAM',           'paused',    3100, 1.40, 3)
ON CONFLICT (id) DO NOTHING;

-- Segments
INSERT INTO segment (id, owner_id, name, age_min, age_max, industry, role, region, size_estimate) VALUES
 ('00000000-0000-0000-0000-00000000d001', :ff, 'Empresas Tecnológicas', 25, 45, 'Tecnología', 'CTO / Director IT', 'LATAM', 48000),
 ('00000000-0000-0000-0000-00000000d002', :ff, 'Educación Superior',    18, 35, 'Educación',  'Docente / Admin',   'Colombia', 96000),
 ('00000000-0000-0000-0000-00000000d003', :ff, 'Gamers Prosumer',       16, 30, 'Gaming / Entretenimiento', 'Usuario Final', 'Global', 210000)
ON CONFLICT (id) DO NOTHING;

-- Assets
INSERT INTO asset (id, owner_id, name, category, tags, file_type, size_kb, status) VALUES
 ('00000000-0000-0000-0000-00000000e001', :ff, 'banner-terminal-pro-1920', 'Banner', 'producto,terminal,pro', 'image/png', 845, 'ready'),
 ('00000000-0000-0000-0000-00000000e002', :ff, 'spot-back-to-school-15s',  'Video',  'educacion,promo',       'video/mp4', 20480, 'ready'),
 ('00000000-0000-0000-0000-00000000e003', :ff, 'carrusel-tech-summit',     'Carrusel','evento,sponsor',       'image/webp', 1230, 'processing')
ON CONFLICT (id) DO NOTHING;

-- Invoices
INSERT INTO invoice (id, user_id, invoice_number, issued_on, concept, amount_cop, credits, status) VALUES
 ('00000000-0000-0000-0000-00000000f001', :ff, 'INV-2026-00128', '2026-05-01', 'Recarga de Créditos - Paquete Grande', 300000, 6000000, 'paid'),
 ('00000000-0000-0000-0000-00000000f002', :ff, 'INV-2026-00112', '2026-04-01', 'Recarga de Créditos - Paquete Grande', 300000, 6000000, 'paid'),
 ('00000000-0000-0000-0000-00000000f003', :ff, 'INV-2025-00230', '2025-10-01', 'Recarga de Créditos - Paquete Pequeño',  10000,   10000, 'rejected')
ON CONFLICT (id) DO NOTHING;

-- API keys (masked — never store the real secret)
INSERT INTO api_key (id, user_id, name, masked_key, environment, last_used) VALUES
 ('00000000-0000-0000-0000-0000000a0001', :ff, 'Producción Marketing', 'cp_live_••••4f2a', 'production',  now() - interval '2 hours'),
 ('00000000-0000-0000-0000-0000000a0002', :ff, 'Pruebas CI',           'cp_test_••••9b71', 'development', now() - interval '5 days')
ON CONFLICT (id) DO NOTHING;

-- QFDM licenses
INSERT INTO qfdm_license (id, user_id, license_key, terminals, plan_type, period, start_date, expiration, status) VALUES
 ('00000000-0000-0000-0000-0000000b0001', :ff, 'VK7JG-NPHTM-C97JM-9MPGT-3V66T', 50,  'Crecimiento', 'Mensual', '2026-05-01', '2026-06-01', 'active'),
 ('00000000-0000-0000-0000-0000000b0002', :ff, 'QJ8XW-LM2RN-D45BT-7FGYH-9KPVR', 200, 'Empresarial', 'Anual',   '2026-04-15', '2027-04-15', 'active'),
 ('00000000-0000-0000-0000-0000000b0003', :ff, 'B3NTD-RF89S-GH2PL-6MK4W-X7ZYQ', 10,  'Estandar',    'Anual',   '2025-11-20', '2026-05-20', 'expired')
ON CONFLICT (id) DO NOTHING;

-- Withdrawals (burn → fiat history). cop_received follows the ledger formula:
-- floor(cofp_burned × 0.29 × (1 + tier_margin)); both rows assume tier2 (+10%),
-- i.e. 0.319 COP/COFP — keep in sync with app/cofp/ledger.py.
INSERT INTO withdrawal (id, user_id, cofp_burned, cop_received, concept, status) VALUES
 ('00000000-0000-0000-0000-0000000c0001', :ff, 50.000000, 15, 'Retiro Tier II', 'paid'),
 ('00000000-0000-0000-0000-0000000c0002', :ff, 40000.000000, 12760, 'Ampliación de almacenamiento', 'pending')
ON CONFLICT (id) DO NOTHING;

COMMIT;
