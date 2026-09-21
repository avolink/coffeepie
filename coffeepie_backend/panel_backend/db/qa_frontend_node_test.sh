#!/usr/bin/env bash
# Replays EXACTLY what the panel's cp-panel-data.js saveNode() sends when a user
# registers a node in the browser: same JSON body, same Origin header, same
# Bearer token from /auth/login. Proves the frontend → backend → DB write path.
set -uo pipefail
B=http://localhost:8000
ORIGIN=http://localhost:5000
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }

echo "── nodes in DB BEFORE ──"
docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie -t -c "SELECT count(*) FROM node;"

# 1) Log in exactly as the modal does (JSON), capture token.
TOK=$(curl -s -X POST "$B/auth/login" -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)
echo "token acquired: ${TOK:0:24}…"

# 2) POST the node EXACTLY as cp-panel-data.js builds it (field names matter).
STAMP=$(date +%H%M%S)
echo "── POST /nodes (as the browser would) ──"
RESP=$(curl -s -w '\n%{http_code}' -X POST "$B/nodes" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"qa-frontend-'"$STAMP"'","public_ip":"10.0.0.177","vcores":12,"ram_gb":40,"ssd_gb":750,"gpu_vram_mb":8192,"hypervisor":"kvm","location":"Barranquilla, CO"}')
echo "  HTTP $(echo "$RESP" | tail -1)"
echo "  CORS allow-origin echoed: (checked via preflight earlier)"

# 3) Confirm it's what GET /nodes returns (what the table renders from).
echo "── GET /nodes now returns ──"
curl -s "$B/nodes" -H "Authorization: Bearer $TOK" \
  | python3 -c "import sys,json;[print(' •',n['name'],'|',n['public_ip'],'|',n['location']) for n in json.load(sys.stdin)]"

echo "── nodes in DB AFTER (ground truth) ──"
docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie -c \
  "SELECT name, public_ip, vcores, ram_gb, hypervisor, created_at FROM node ORDER BY created_at DESC LIMIT 3;"
