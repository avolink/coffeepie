#!/usr/bin/env bash
# QA test for the hardware-probe / anti-lying node capacity flow (port 8000).
# Verifies: probe is deterministic, and create/patch IGNORE client-sent capacity
# (a DC admin cannot over-declare how many Slices a node serves).
set -uo pipefail
B=http://127.0.0.1:8000

jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }

echo "=== login provider@qa.coffeepie.co ==="
TOKEN=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"provider@qa.coffeepie.co","password":"testing"}' | jqget access_token)
echo "  token_len=${#TOKEN}"
AUTH=(-H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json')

echo "=== 1. probe 190.0.0.50 ==="
P1=$(curl -s -X POST "$B/nodes/probe" "${AUTH[@]}" -d '{"public_ip":"190.0.0.50","hypervisor":"proxmox"}')
echo "  $P1"

echo "=== 2. probe 190.0.0.50 again (must be identical) ==="
P2=$(curl -s -X POST "$B/nodes/probe" "${AUTH[@]}" -d '{"public_ip":"190.0.0.50","hypervisor":"proxmox"}')
echo "  $P2"
[ "$P1" = "$P2" ] && echo "  PASS deterministic" || echo "  FAIL not deterministic"

echo "=== 3. probe a DIFFERENT ip (should differ) ==="
P3=$(curl -s -X POST "$B/nodes/probe" "${AUTH[@]}" -d '{"public_ip":"45.12.9.7","hypervisor":"proxmox"}')
echo "  $P3"

echo "=== 4. CREATE with in-bounds LIE (vcores=4096, hypervisor=xen) — server must overwrite ==="
CREATED=$(curl -s -X POST "$B/nodes" "${AUTH[@]}" \
  -d '{"name":"QA-AntiLie-Node","public_ip":"190.0.0.50","vcores":4096,"ram_gb":65000,"ssd_gb":1000000,"gpu_vram_mb":1000000,"hypervisor":"xen","location":"QA"}')
echo "  $CREATED"
NID=$(echo "$CREATED" | jqget id)
STORED_CORES=$(echo "$CREATED" | jqget vcores)
PROBE_CORES=$(echo "$P1" | jqget vcores)
STORED_HV=$(echo "$CREATED" | jqget hypervisor)
PROBE_HV=$(echo "$P1" | jqget hypervisor)
echo "  stored vcores=$STORED_CORES (probe=$PROBE_CORES)  stored hv=$STORED_HV (detected=$PROBE_HV, sent=xen)"
if [ -n "$STORED_CORES" ] && [ "$STORED_CORES" = "$PROBE_CORES" ] && [ "$STORED_CORES" != "4096" ]; then
  echo "  PASS capacity: server ignored the lie, stored measured value"
else
  echo "  FAIL capacity: lie was accepted"
fi
if [ -n "$STORED_HV" ] && [ "$STORED_HV" = "$PROBE_HV" ] && [ "$STORED_HV" != "xen" ]; then
  echo "  PASS hypervisor: server ignored 'xen', stored detected '$STORED_HV'"
else
  echo "  FAIL hypervisor: client value was accepted"
fi

echo "=== 5. cleanup ==="
if [ -n "$NID" ]; then
  curl -s -o /dev/null -w "  delete HTTP %{http_code}\n" -X DELETE "$B/nodes/$NID" -H "Authorization: Bearer $TOKEN"
fi
