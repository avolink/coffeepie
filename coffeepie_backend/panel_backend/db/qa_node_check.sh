#!/usr/bin/env bash
# Verify the node write path: POST /nodes persists, survives, and is deletable.
set -uo pipefail
B=http://localhost:8000
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }

TOK=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)

echo "=== POST /nodes (register) ==="
RESP=$(curl -s -w '\n%{http_code}' -X POST "$B/nodes" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"qa-node-via-api-1","public_ip":"10.0.0.150","vcores":24,"ram_gb":96,"ssd_gb":2000,"gpu_vram_mb":12288,"hypervisor":"proxmox","location":"Bogotá, CO"}')
echo "$RESP" | tail -1 | sed 's/^/  HTTP /'
NODE_ID=$(echo "$RESP" | head -1 | jqget id)
echo "  id: $NODE_ID"

echo "=== invalid IP must be rejected (expect 400) ==="
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$B/nodes" \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"bad","public_ip":"not-an-ip","vcores":1,"ram_gb":1,"ssd_gb":1}'

echo "=== advertiser may NOT register nodes (expect 403) ==="
ATOK=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"advertiser@qa.coffeepie.co","password":"testing"}' | jqget access_token)
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$B/nodes" \
  -H "Authorization: Bearer $ATOK" -H 'Content-Type: application/json' \
  -d '{"name":"x","public_ip":"10.0.0.1","vcores":1,"ram_gb":1,"ssd_gb":1}'

echo "=== ground truth in Postgres ==="
docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie -t -c \
  "SELECT name, provider_id, created_at FROM node ORDER BY created_at;"
