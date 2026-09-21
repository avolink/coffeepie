#!/usr/bin/env bash
# Verify every panel-data endpoint returns seeded rows for testing@.
set -uo pipefail
B=http://localhost:8000
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }
TOK=$(curl -s -X POST "$B/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)

for ep in campaigns segments assets invoices apikeys licenses withdrawals; do
  N=$(curl -s "$B/panel/$ep" -H "Authorization: Bearer $TOK" \
      | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d) if isinstance(d,list) else 'ERR '+str(d))")
  echo "  /panel/$ep → $N rows"
done
echo "── sample: first campaign ──"
curl -s "$B/panel/campaigns" -H "Authorization: Bearer $TOK" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d[0] if d else 'none')"
