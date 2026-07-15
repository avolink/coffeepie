-- ── 0005: ad serving + Cr credit ledger ───────────────────────────────────
-- The watch-ads-for-credits loop: advertisers run campaigns (panel Campañas /
-- Segmentación); consumers watch the best-suited ad and earn Cr. The ledger
-- is the real Cr wallet — Saldo = SUM(delta_cr).

-- Audience profile used for ad targeting (matched against segment fields:
-- age_min/age_max, industry, role, region). Shape:
--   {"age": 31, "role": "Mamá", "region": "Colombia",
--    "interests": ["Bebés y Maternidad", "Hogar"]}
ALTER TABLE app_user ADD COLUMN IF NOT EXISTS audience JSONB;

-- One row per completed ad view. campaign_id NULL = house ad (no campaign
-- inventory matched; Coffee Pie's own promo filled the slot).
CREATE TABLE IF NOT EXISTS ad_impression (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaign(id) ON DELETE SET NULL,
    reward_cr   NUMERIC NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ad_impression_user ON ad_impression (user_id);
CREATE INDEX IF NOT EXISTS ix_ad_impression_campaign ON ad_impression (campaign_id);

-- Cr wallet (consumer currency — distinct from COFP, the provider token).
CREATE TABLE IF NOT EXISTS credit_ledger (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    delta_cr   NUMERIC NOT NULL,
    reason     TEXT NOT NULL,            -- 'signup_bonus' | 'ad_reward' | 'topup' | 'vm_usage' …
    ref        UUID,                     -- e.g. ad_impression.id / vm.id
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_credit_ledger_user ON credit_ledger (user_id);

ALTER TABLE ad_impression ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_impressions ON ad_impression;
CREATE POLICY own_impressions ON ad_impression FOR SELECT USING (user_id = auth.uid());

ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_ledger ON credit_ledger;
CREATE POLICY own_ledger ON credit_ledger FOR SELECT USING (user_id = auth.uid());
