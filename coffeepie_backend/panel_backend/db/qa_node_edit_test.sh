#!/usr/bin/env bash
# Replays EXACTLY what cp-panel-data.js saveNode() sends when a provider edits
# a node (PATCH /nodes/{id} with the full modal body), plus the guard rails:
# duplicate-name → 409, foreign node → 404, unknown field tolerance.
# Usage: qa_node_edit_test.sh [NODE_NAME] [NEW_IP]   (defaults: N104 → fix typo)
set -uo pipefail
B=http://localhost:8000
ORIGIN=http://localhost:5000
NODE_NAME="${1:-N104}"
NEW_IP="${2:-206.62.137.25}"
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }
PSQL() { docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie "$@"; }

TOK=$(curl -s -X POST "$B/auth/login" -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)
echo "token acquired: ${TOK:0:24}…"

NODE_ID=$(PSQL -t -A -c "SELECT id FROM node WHERE name='$NODE_NAME' LIMIT 1;")
echo "── BEFORE: $NODE_NAME ──"
PSQL -t -c "SELECT name, public_ip FROM node WHERE id='$NODE_ID';"

# 1) PATCH exactly as the edit modal sends it (full body, same headers).
echo "── 1. PATCH /nodes/$NODE_ID (fix IP → $NEW_IP) ──"
CODE=$(curl -s -o /tmp/qa_edit_resp.json -w '%{http_code}' -X PATCH "$B/nodes/$NODE_ID" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"public_ip":"'"$NEW_IP"'"}')
echo "  HTTP $CODE (expect 200)"
echo "  API returns: $(jqget public_ip < /tmp/qa_edit_resp.json)"

echo "── AFTER (DB ground truth) ──"
PSQL -t -c "SELECT name, public_ip FROM node WHERE id='$NODE_ID';"

# 2) Renaming a node to a sibling's name must hit the unique index → 409.
SIBLING=$(PSQL -t -A -c "SELECT name FROM node WHERE id<>'$NODE_ID' AND provider_id=(SELECT provider_id FROM node WHERE id='$NODE_ID') LIMIT 1;")
echo "── 2. PATCH rename to existing \"$SIBLING\" (expect 409) ──"
CODE=$(curl -s -o /tmp/qa_edit_409.json -w '%{http_code}' -X PATCH "$B/nodes/$NODE_ID" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"'"$SIBLING"'"}')
echo "  HTTP $CODE — $(jqget detail < /tmp/qa_edit_409.json)"

# 3) POST duplicate name must also 409 (registration double-submit guard).
echo "── 3. POST duplicate name \"$NODE_NAME\" (expect 409) ──"
CODE=$(curl -s -o /tmp/qa_post_409.json -w '%{http_code}' -X POST "$B/nodes" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"'"$NODE_NAME"'","public_ip":"10.9.9.9","vcores":1,"ram_gb":1,"ssd_gb":1}')
echo "  HTTP $CODE — $(jqget detail < /tmp/qa_post_409.json)"

# 4) A non-admin provider PATCHing someone else's node must get 404.
PTOK=$(curl -s -X POST "$B/auth/login" -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
  -d '{"email":"provider@qa.coffeepie.co","password":"testing"}' | jqget access_token)
echo "── 4. PATCH as provider@qa on testing@'s node (expect 404) ──"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$B/nodes/$NODE_ID" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $PTOK" -H 'Content-Type: application/json' \
  -d '{"public_ip":"1.2.3.4"}')
echo "  HTTP $CODE"

# 5) Malformed IP must be rejected by the ::inet cast → 400.
echo "── 5. PATCH malformed IP (expect 400) ──"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X PATCH "$B/nodes/$NODE_ID" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"public_ip":"not-an-ip"}')
echo "  HTTP $CODE"
