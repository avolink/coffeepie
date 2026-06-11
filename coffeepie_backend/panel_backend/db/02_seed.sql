-- Coffee Pie Panel — QA seed data.
--
-- Deterministic UUIDs so the prototype/frontend can reference fixed test users.
-- Gives the panel real numbers to render during QA. Re-runnable (idempotent).

BEGIN;

-- ── Test users, one per role (+ an admin and a multi-role user) ─────────
INSERT INTO app_user (id, email, display_name) VALUES
    ('00000000-0000-0000-0000-0000000000a1', 'advertiser@qa.coffeepie.co',   'QA Advertiser'),
    ('00000000-0000-0000-0000-0000000000a2', 'manufacturer@qa.coffeepie.co', 'QA Manufacturer'),
    ('00000000-0000-0000-0000-0000000000a3', 'provider@qa.coffeepie.co',     'QA Provider'),
    ('00000000-0000-0000-0000-0000000000a4', 'contributor@qa.coffeepie.co',  'QA Contributor'),
    ('00000000-0000-0000-0000-0000000000a5', 'admin@qa.coffeepie.co',        'QA Admin'),
    ('00000000-0000-0000-0000-0000000000a6', 'prosumer@qa.coffeepie.co',     'QA Prosumer (provider+advertiser)')
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_role (user_id, role) VALUES
    ('00000000-0000-0000-0000-0000000000a1', 'advertiser'),
    ('00000000-0000-0000-0000-0000000000a2', 'manufacturer'),
    ('00000000-0000-0000-0000-0000000000a3', 'provider'),
    ('00000000-0000-0000-0000-0000000000a4', 'contributor'),
    ('00000000-0000-0000-0000-0000000000a5', 'admin'),
    ('00000000-0000-0000-0000-0000000000a6', 'provider'),
    ('00000000-0000-0000-0000-0000000000a6', 'advertiser')
ON CONFLICT DO NOTHING;

-- ── Ledger fixtures ─────────────────────────────────────────────────────
-- Provider 'a3' earned COFP from served slices. dedup_key guards each accrual.
-- 4 slices * 30 min = 120 COFP, then 8 slices * 15 min = 120 COFP.
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, instance_id, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000a3', 'accrual', 120.000000,
     'slice-minutes effectively served', 'cp-qa-instance-1', 'cp-qa-instance-1:2026-06-11T10:00'),
    ('00000000-0000-0000-0000-0000000000a3', 'accrual', 120.000000,
     'slice-minutes effectively served', 'cp-qa-instance-2', 'cp-qa-instance-2:2026-06-11T11:00')
ON CONFLICT (dedup_key) DO NOTHING;

-- Contributor 'a4' holds COFP (→ voting power). Granted via an audited adjustment.
INSERT INTO ledger_entry (account_id, entry_type, amount, reason, dedup_key) VALUES
    ('00000000-0000-0000-0000-0000000000a4', 'adjustment', 500.000000,
     'QA seed: contributor governance stake', 'qa-seed-contributor-a4')
ON CONFLICT (dedup_key) DO NOTHING;

-- ── Provider nodes (the Proveedores tab table) ─────────────────────────
INSERT INTO node (id, provider_id, name, public_ip, vcores, ram_gb, ssd_gb, gpu_vram_mb, hypervisor, location, status) VALUES
    ('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-0000000000a3',
     'qa-node-bogota-1', '10.0.0.11', 20, 64, 1024, 8192, 'proxmox', 'Bogotá, CO', 'active'),
    ('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000a3',
     'qa-node-medellin-1', '10.0.0.12', 32, 128, 2048, 16384, 'proxmox', 'Medellín, CO', 'maintenance')
ON CONFLICT (id) DO NOTHING;

COMMIT;

-- Quick QA sanity checks (run manually):
--   SELECT * FROM account_balance ORDER BY account_id;
--   -- expect a3 = 240.000000, a4 = 500.000000
--   SELECT email, array_agg(role) FROM app_user u JOIN user_role r ON r.user_id=u.id GROUP BY email;
