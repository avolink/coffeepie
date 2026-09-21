#!/usr/bin/env bash
# Replays EXACTLY what cp-panel-data.js requestWithdrawal() sends, then proves:
#   burn lands in ledger_entry, history row lands in withdrawal (status pending,
#   linked by ledger_entry_id), GET /panel/withdrawals returns it, balance drops,
#   and an over-balance request is rejected with 400 leaving NO rows behind.
# Usage: qa_withdraw_test.sh [AMOUNT] [TIER]   (defaults: 100000 tier2 — the minimum)
set -uo pipefail
B=http://localhost:8000
ORIGIN=http://localhost:5000
AMOUNT="${1:-100000}"
TIER="${2:-tier2}"
jqget() { python3 -c "import sys,json;print(json.load(sys.stdin).get('$1',''))"; }
PSQL() { docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie "$@"; }

TOK=$(curl -s -X POST "$B/auth/login" -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
  -d '{"email":"testing@coffeepie.co","password":"testing"}' | jqget access_token)
echo "token acquired: ${TOK:0:24}…"

BAL_BEFORE=$(curl -s "$B/cofp/balance" -H "Authorization: Bearer $TOK" | jqget cofp_balance)
WD_BEFORE=$(PSQL -t -A -c "SELECT count(*) FROM withdrawal;")
echo "── BEFORE: balance=$BAL_BEFORE COFP, withdrawal rows=$WD_BEFORE ──"

# 1) POST exactly as the form sends it.
echo "── 1. POST /cofp/withdraw ($AMOUNT COFP, $TIER) ──"
CODE=$(curl -s -o /tmp/qa_wd.json -w '%{http_code}' -X POST "$B/cofp/withdraw" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"cofp_amount":"'"$AMOUNT"'","tier":"'"$TIER"'","concept":"QA retiro automatizado"}')
ENTRY=$(jqget ledger_entry_id < /tmp/qa_wd.json)
echo "  HTTP $CODE (expect 200) — burned $(jqget cofp_burned < /tmp/qa_wd.json) COFP → $(jqget payout_cop < /tmp/qa_wd.json) COP"
echo "  ledger_entry_id: $ENTRY"

# 2) Ground truth: ledger burn + linked history row.
echo "── 2. DB ground truth (burn ↔ history linked) ──"
PSQL -c "SELECT w.cofp_burned, w.cop_received, w.concept, w.status,
                l.entry_type, l.amount AS ledger_amount
         FROM withdrawal w JOIN ledger_entry l ON l.id = w.ledger_entry_id
         WHERE w.ledger_entry_id = '$ENTRY';"

# 3) The panel's history endpoint shows it.
echo "── 3. GET /panel/withdrawals (what the table renders) ──"
curl -s "$B/panel/withdrawals" -H "Authorization: Bearer $TOK" \
  | python3 -c "import sys,json;[print(' •',r['cofp_burned'],'COFP →',r['cop_received'],'COP |',r['concept'],'|',r['status']) for r in json.load(sys.stdin)[:3]]"

# 4) Balance dropped by exactly AMOUNT.
BAL_AFTER=$(curl -s "$B/cofp/balance" -H "Authorization: Bearer $TOK" | jqget cofp_balance)
echo "── 4. balance $BAL_BEFORE → $BAL_AFTER (expect -$AMOUNT) ──"

# 5) Over-balance request → 400, and NO ledger/history rows created.
echo "── 5. POST 999999999999 COFP (expect 400 insufficient, no rows) ──"
CODE=$(curl -s -o /tmp/qa_wd_400.json -w '%{http_code}' -X POST "$B/cofp/withdraw" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"cofp_amount":"999999999999","tier":"'"$TIER"'","concept":"should fail"}')
echo "  HTTP $CODE — $(jqget detail < /tmp/qa_wd_400.json)"

# 6) Per-withdrawal settlement cap: 100M+1 → 400 even with enough balance.
echo "── 6. POST 100000001 COFP (expect 400 cap, no rows) ──"
CODE=$(curl -s -o /tmp/qa_wd_cap.json -w '%{http_code}' -X POST "$B/cofp/withdraw" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"cofp_amount":"100000001","tier":"'"$TIER"'","concept":"should hit the cap"}')
echo "  HTTP $CODE — $(jqget detail < /tmp/qa_wd_cap.json)"

# 7) Per-withdrawal floor: 99999 → 400 (bank transfer costs eat dust payouts).
echo "── 7. POST 99999 COFP (expect 400 below minimum, no rows) ──"
CODE=$(curl -s -o /tmp/qa_wd_min.json -w '%{http_code}' -X POST "$B/cofp/withdraw" \
  -H "Origin: $ORIGIN" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"cofp_amount":"99999","tier":"'"$TIER"'","concept":"should hit the floor"}')
echo "  HTTP $CODE — $(jqget detail < /tmp/qa_wd_min.json)"
WD_AFTER=$(PSQL -t -A -c "SELECT count(*) FROM withdrawal;")
echo "  withdrawal rows: $WD_BEFORE → $WD_AFTER (expect +1 total, none from the 400s)"
