#!/usr/bin/env bash
# Verify the gated panel flow for testing@coffeepie.co with seeded data.
set -uo pipefail
B=http://localhost:8000
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }

echo "=== reject a non-existent credential (expect 401) ==="
curl -s -o /dev/null -w "  ghost@nope.co/x → HTTP %{http_code}\n" -X POST "$B/auth/login" \
  -H 'Content-Type: application/json' -d '{"email":"ghost@nope.co","password":"x"}'

echo "=== reject testing@ with wrong password (expect 401) ==="
curl -s -o /dev/null -w "  testing@/wrong → HTTP %{http_code}\n" -X POST "$B/auth/login" \
  -H 'Content-Type: application/json' -d '{"email":"testing@coffeepie.co","password":"wrong"}'

echo "=== accept testing@/testing, then read seeded data ==="
TOK=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)
echo "  balance:        $(curl -s "$B/cofp/balance" -H "Authorization: Bearer $TOK")"
echo "  provider summ.: $(curl -s "$B/cofp/provider/summary" -H "Authorization: Bearer $TOK")"
echo "  voting power:   $(curl -s "$B/cofp/governance/voting-power" -H "Authorization: Bearer $TOK")"
