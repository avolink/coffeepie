-- ── 0004: per-user virtual machines on QFDM nodes ─────────────────────────
-- One row per machine a consumer has created. The Slice ("Porción") is the
-- atomic capacity unit: 1 slice = 1 vCore + 1 GB RAM (QFDM quantization).
-- status lifecycle: creating → created → running ⇄ stopped   (error terminal)

CREATE TABLE IF NOT EXISTS vm (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    node_id       UUID REFERENCES node(id) ON DELETE SET NULL,
    proxmox_vmid  INTEGER,                    -- vmid on the node's hypervisor
    name          TEXT NOT NULL DEFAULT 'Mi Máquina',
    os            TEXT NOT NULL,              -- catalog key: bodhi|mint|win10|…
    slices        INTEGER NOT NULL CHECK (slices >= 1),
    recurrence    TEXT NOT NULL DEFAULT 'minute'
                  CHECK (recurrence IN ('minute', 'month', 'year')),
    rate_cr_min   NUMERIC NOT NULL DEFAULT 0, -- Cr per minute (slices × base)
    status        TEXT NOT NULL DEFAULT 'creating'
                  CHECK (status IN ('creating', 'created', 'running', 'stopped', 'error')),
    error_detail  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_vm_owner ON vm (owner_id);
CREATE INDEX IF NOT EXISTS ix_vm_node  ON vm (node_id);

ALTER TABLE vm ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS own_vms ON vm;
CREATE POLICY own_vms ON vm FOR ALL USING (owner_id = auth.uid());
