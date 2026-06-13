# Coffee Pie Disaster Recovery Runbook

Procedures for recovering Coffee Pie infrastructure from common failure scenarios.
Integrates with `EMERGENCY_PROTOCOL.md` for security incidents.

## Recovery Time Objectives (RTO) — Targets

> **Note:** These are target objectives for production operations. Actual recovery times have not yet been validated through quarterly DR drills at current alpha scale.

| Component | RTO | RPO |
|-----------|-----|-----|
| Orchestrator | 15 min | 0 (streaming replica) |
| DC Agent | 5 min | 0 (stateless) |
| PostgreSQL | 15 min | < 1 min (WAL streaming) |
| Actor (per VM) | 2 min | 0 (orchestrator reassigns) |
| Sunshine | 2 min | 0 (stateless) |
| Codec Terminal | Instant | 0 (reconnect to orchestrator) |

---

## Scenario 1: Orchestrator Down

**Symptoms:** Codec terminals can't connect, API returns 502/503, healthd alerts.

### Recovery Steps

```bash
# 1. Verify it's actually down
coffeepie-healthd --strict

# 2. Check logs
docker compose logs orchestrator --tail=100  # Docker deployment
# OR
journalctl -u coffeepie-orchestrator -n 100 --no-pager  # Systemd deployment

# 3. Common causes & fixes:

# A. OOM killed
dmesg | grep -i "out of memory"
# Fix: docker compose up -d orchestrator  (restarts with restart: unless-stopped)
# OR: systemctl restart coffeepie-orchestrator

# B. Database connection lost
docker compose exec orchestrator python manage.py check --database default
# Fix: restart postgres first, then orchestrator
docker compose restart postgres
sleep 5
docker compose restart orchestrator

# C. Port conflict
ss -tlnp | grep 8000
# Fix: kill conflicting process, restart

# 4. Verify recovery
curl -s http://localhost:***coffeepie-healthd --once
```

### If orchestrator can't be recovered in-place:

```bash
# Promote streaming replica
ssh postgres-replica "pg_ctl promote"
# Update DNS/load balancer to point to standby orchestrator
# Rebuild failed orchestrator from backup
```

---

## Scenario 2: Database Corruption

**Symptoms:** Orchestrator returns 500, migrations fail, data inconsistency.

### Recovery Steps

```bash
# 1. Stop orchestrator immediately (prevents further writes)
docker compose stop orchestrator

# 2. Check PostgreSQL logs
docker compose logs postgres --tail=200

# 3. Attempt recovery from WAL
docker compose exec postgres pg_ctl restart -D /var/lib/postgresql/data

# 4. If WAL recovery fails, restore from backup
# List available backups
docker compose exec postgres ls -la /backups/

# Restore latest
LATEST=$(docker compose exec -T postgres ls -t /backups/ | head -1)
docker compose exec -T postgres pg_restore -d coffeepie /backups/$LATEST

# 5. Apply WAL to catch up to point-of-failure
docker compose exec postgres pg_rewind --target-pgdata=/var/lib/postgresql/data \
  --source-server="host=replica port=5432"

# 6. Restart orchestrator
docker compose start orchestrator
docker compose exec orchestrator python manage.py migrate --noinput

# 7. Verify
docker compose exec orchestrator python manage.py check
coffeepie-healthd --once
```

---

## Scenario 3: Sunshine Stream Failure

**Symptoms:** Users report black screen, frozen stream, or disconnection.

### Per-VM Recovery

```bash
# 1. Identify affected VM
curl -s http://localhost:9090/api/v1/nodes/pve-A/vms | jq '.vms[] | select(.status != "running")'

# 2. Check Sunshine on VM
ssh root@10.0.0.50 "systemctl status sunshine"

# 3. Restart Sunshine
ssh root@10.0.0.50 "systemctl restart sunshine"

# 4. Verify stream recovered
coffeepie-stream-monitor --once

# 5. If restart doesn't fix:
# A. Check GPU encoder
ssh root@10.0.0.50 "nvidia-smi"  # or vainfo for AMD/Intel

# B. Check for GPU memory leak
ssh root@10.0.0.50 "nvidia-smi --query-gpu=memory.used --format=csv"

# C. Reboot VM (last resort)
curl -X POST http://localhost:9090/api/v1/nodes/pve-A/vms/200/reset \
  -H "Authorization: Bearer ${DC_AGENT_TOKEN}"
```

### Mass Stream Failure (all streams down)

```bash
# 1. Check DC Agent
curl -s http://localhost:9090/health

# 2. Check Proxmox hypervisor
curl -s http://localhost:8001/health

# 3. If hypervisor is down:
# Proxmox HA should auto-migrate VMs to healthy nodes
# Check Proxmox cluster status
ssh root@pve-A "pvecm status"
ssh root@pve-A "ha-manager status"

# 4. Manual VM migration if HA didn't trigger
ssh root@pve-A "qm migrate 200 pve-B --online"
```

---

## Scenario 4: Network Partition

**Symptoms:** Some nodes unreachable, split-brain in orchestrator, partial outages.

### Recovery Steps

```bash
# 1. Identify partition boundary
coffeepie-network-health <each-node-ip>
# Which nodes can reach which others?

# 2. If L2 VLAN broken:
ssh core-switch "show vlan 100"  # Coffee Pie VLAN
ssh core-switch "show interfaces trunk"

# 3. If BGP/OSPF routing issue:
ssh router "show ip route 10.0.0.0/16"
ssh router "clear ip route *"

# 4. Once network restored, restart affected services:
docker compose restart dc-agent actor

# 5. Verify full connectivity
for node in $(cat nodes.txt); do
    coffeepie-network-health $node
done
```

---

## Scenario 5: Codec Terminal Mass Disconnect

**Symptoms:** Many users disconnected simultaneously, support tickets spike.

### Recovery Steps

```bash
# 1. Check orchestrator capacity
curl -s http://localhost:8000/uds/rest/transports/ | jq length

# 2. Check DC Agent slice availability
curl -s http://localhost:9090/capacity

# 3. If out of capacity:
# A. Scale up: deploy more VMs
coffeepie-deploy --phase 2 --target root@new-pve-node

# B. Reduce per-user slices temporarily
# (Update orchestrator config: max_slices_per_user)

# 4. Notify users via status page
# Update: https://status.coffeepie.co

# 5. Queue reconnection to avoid thundering herd
# Orchestrator handles this automatically with exponential backoff
```

---

## Scenario 6: Legal Entity or Sanctions Risk

**Symptoms:** Colombian legal entity (GRUPO 3P1 COLOMBIA S.A.S.) subject to sanctions (OFAC, Colombian SFC), regulatory investigation, or corporate dissolution. BVC listing blocked or revoked.

### Recovery Steps

```bash
# 1. Assess scope
# - Does the sanction freeze the entity's bank accounts?
# - Are provider fiat settlements blocked?
# - Can the entity continue operating while resolving the issue?

# 2. Activate legal counsel
# Contact: legal@coffeepie.co
# Engage external counsel specialized in sanctions/regulatory defense

# 3. Short-term continuity (if entity frozen)
# A. Community-operated infrastructure continues under open-source licenses
# B. Providers continue earning COFP (on-chain, no bank needed)
# C. Provider fiat settlements paused — communicate timeline to providers
# D. Credit purchases via third-party payment processors if unaffected

# 4. Medium-term restructuring options
# A. Establish foreign subsidiary in neutral jurisdiction
# B. Transfer IP/assets to a foundation structure (Swiss Stiftung or similar)
# C. DAO wrapper for governance continuity
# D. Alternative exchange listing (non-Colombian) if BVC is blocked

# 5. Communication
# Update: https://status.coffeepie.co
# Notify: providers, investors, community via Discord and email
# Transparency: publish summary of situation and recovery plan
```

### Prevention

- [ ] Foreign subsidiary or foundation established as contingency vehicle
- [ ] Multi-jurisdiction banking relationships (not solely Colombian)
- [ ] Backup exchange listing plan documented (beyond BVC)
- [ ] IP/patent transfer procedure defined and legally reviewed
- [ ] Key-man risk: succession plan for founder and core team roles

---

## Backup & Restore Procedures

### Automated Backups (cron)

```bash
#!/bin/bash
# /etc/cron.daily/coffeepie-backup
BACKUP_DIR="/backups/coffeepie"
mkdir -p $BACKUP_DIR

DATE=$(date +%Y%m%d-%H%M%S)

# PostgreSQL
docker compose exec -T postgres pg_dump -U coffeepie coffeepie | gzip > $BACKUP_DIR/db-$DATE.sql.gz

# Orchestrator config
tar -czf $BACKUP_DIR/orchestrator-$DATE.tar.gz \
  /etc/coffeepie/ \
  /etc/coffeepie/tls/ \
  docker-compose.yml .env

# Cleanup old backups (> 30 days)
find $BACKUP_DIR -mtime +30 -delete

echo "Backup complete: $DATE"
```

### Restore from Backup

```bash
# 1. Restore database
gunzip -c /backups/coffeepie/db-20260530-000000.sql.gz | \
  docker compose exec -T postgres psql -U coffeepie coffeepie

# 2. Restore config
tar -xzf /backups/coffeepie/orchestrator-20260530-000000.tar.gz -C /

# 3. Verify
docker compose restart orchestrator
coffeepie-healthd --once
```

---

## Testing DR Readiness

### Quarterly DR Drill

```bash
# 1. Simulate orchestrator failure
docker compose stop orchestrator
sleep 30

# 2. Verify healthd alerts
coffeepie-healthd --strict && echo "FAIL: should have alerted" || echo "PASS: alert fired"

# 3. Execute recovery procedure
docker compose start orchestrator
sleep 10

# 4. Verify full recovery
coffeepie-healthd --once
coffeepie-stream-monitor --once

# 5. Document: time to detect, time to recover, any manual steps needed
echo "DR Drill $(date): RTO achieved in X minutes" >> /var/log/coffeepie/dr-drill.log
```

### Validation Checklist

- [ ] Backups running daily
- [ ] Backup restoration tested within last 30 days
- [ ] Streaming replica in sync (< 1 second lag)
- [ ] DR runbook reviewed and updated this quarter
- [ ] Team knows their DR roles (who restores what)
- [ ] Emergency contact list current
- [ ] Off-site backup copy exists (different DC or cloud)
