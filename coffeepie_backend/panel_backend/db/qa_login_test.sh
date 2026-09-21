#!/usr/bin/env bash
# End-to-end QA login test against the running backend (port 8000) + test DB.
set -uo pipefail
B=http://127.0.0.1:8000

jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }

echo "=== 1. LOGIN testing@coffeepie.co / testing (correct) ==="
RESP=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}')
echo "  uid:   $(echo "$RESP" | jqget uid)"
echo "  email: $(echo "$RESP" | jqget email)"
echo "  roles: $(echo "$RESP" | jqget roles)"
TOKEN=$(echo "$RESP" | jqget access_token)
echo "  token: ${TOKEN:0:36}..."

echo
echo "=== 2. LOGIN wrong password (expect HTTP 401) ==="
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -X POST "$B/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"wrong"}'

echo
echo "=== 3. Token on protected /cofp/balance (admin passes; expect 200) ==="
curl -s -w "\n  HTTP %{http_code}\n" "$B/cofp/balance" -H "Authorization: Bearer $TOKEN"

echo
echo "=== 4. No token on /cofp/balance (expect 401/403) ==="
curl -s -o /dev/null -w "  HTTP %{http_code}\n" "$B/cofp/balance"

echo
echo "=== 5. LOGIN provider@qa.coffeepie.co / testing, then /cofp/provider/summary ==="
PRESP=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"provider@qa.coffeepie.co","password":"testing"}')
echo "  roles: $(echo "$PRESP" | jqget roles)"
PTOKEN=$(echo "$PRESP" | jqget access_token)
curl -s -w "\n  HTTP %{http_code}\n" "$B/cofp/provider/summary" -H "Authorization: Bearer $PTOKEN"

echo
echo "=== 6. Advertiser hitting provider-only endpoint (expect 403) ==="
ARESP=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"advertiser@qa.coffeepie.co","password":"testing"}')
ATOKEN=$(echo "$ARESP" | jqget access_token)
curl -s -o /dev/null -w "  HTTP %{http_code}\n" "$B/cofp/provider/summary" -H "Authorization: Bearer $ATOKEN"
