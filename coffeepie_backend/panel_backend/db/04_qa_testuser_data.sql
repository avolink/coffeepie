-- Coffee Pie Panel — QA data for the memorable test user (testing@coffeepie.co).
--
-- Gives 'testing@coffeepie.co' (uid ...ff) real, varied data so QA can see the
-- panel's logic working end-to-end. Idempotent (dedup_key / ON CONFLICT).
--
-- ⚠️ QA ONLY. Depends on 01_schema.sql, 02_seed.sql, 03_qa_auth.sql.

BEGIN;

-- Make the test user a Provider too (it's already admin), so role-specific
-- panel views render with this account's own data.
INSERT INTO user_role (user_id, role) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'provider'),
    ('00000000-0000-0000-0000-0000000000ff', 'contributor')
ON CONFLICT DO NOTHING;

-- COFP accruals (served slice-minutes) — varied amounts across "instances".
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, instance_id, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'accrual',  96.000000,
     'slice-minutes effectively served', 'cp-qa-ff-1', 'cp-qa-ff-1:2026-06-10T09:00'),
    ('00000000-0000-0000-0000-0000000000ff', 'accrual',  54.500000,
     'slice-minutes effectively served', 'cp-qa-ff-2', 'cp-qa-ff-2:2026-06-10T14:30'),
    ('00000000-0000-0000-0000-0000000000ff', 'accrual', 120.250000,
     'slice-minutes effectively served', 'cp-qa-ff-3', 'cp-qa-ff-3:2026-06-11T08:15')
ON CONFLICT (dedup_key) DO NOTHING;

-- One withdrawal (burn) so balance != raw accrual sum and history looks real.
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'withdrawal', -50.000000,
     'burn→fiat @ 0.319 COP/COFP (tier2)', 'qa-ff-withdraw-1')
ON CONFLICT (dedup_key) DO NOTHING;
-- Net balance for ff: 96 + 54.5 + 120.25 - 50 = 220.750000 COFP.

-- QA top-up: a fat audited adjustment so QA can exercise repeated withdrawals
-- and 7-digit balance rendering (apostrophe formatting) in every viewport.
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'adjustment', 1000000.000000,
     'QA top-up — withdrawal flow testing', 'qa-ff-topup-1')
ON CONFLICT (dedup_key) DO NOTHING;

-- Second top-up: one average rack-month of accruals (20 nodes × 256 slices ×
-- 43'200 min = 221'184'000 slice·min), so QA can test the 100M per-withdrawal
-- settlement cap (MAX_WITHDRAWAL_COFP) from both sides at realistic scale.
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000ff', 'adjustment', 221184000.000000,
     'QA top-up — one average rack-month (20 nodes × 256 slices × 30d)', 'qa-ff-topup-2')
ON CONFLICT (dedup_key) DO NOTHING;
-- Net balance for ff after both top-ups: 222'184'220.75 COFP minus QA burns.

-- A node owned by the test user (Proveedores tab).
INSERT INTO node (id, provider_id, name, public_ip, vcores, ram_gb, ssd_gb, gpu_vram_mb, hypervisor, location, status) VALUES
    ('00000000-0000-0000-0000-0000000000bf', '00000000-0000-0000-0000-0000000000ff',
     'qa-node-testing-1', '10.0.0.99', 16, 48, 512, 6144, 'proxmox', 'Cali, CO', 'active')
ON CONFLICT (id) DO NOTHING;

COMMIT;
