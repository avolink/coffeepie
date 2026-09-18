#!/usr/bin/env bash
# Start the panel backend for QA against the local test DB.
set -uo pipefail
cd "$(dirname "$0")/.."

pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 1

export PYTHONPATH=.qa_libs:.
export QA_LOCAL_AUTH=true
export AUTH_PROVIDER=supabase
export SUPABASE_JWT_SECRET=qa-local-secret-not-for-prod
export PANEL_DB_DRIVER=pg8000
export LEDGER_BACKEND=postgres
export DATABASE_URL=postgresql://coffeepie:coffeepie_dev@127.0.0.1:5432/coffeepie

nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/panel_api.log 2>&1 &
echo "uvicorn pid $!"

for _ in $(seq 1 15); do
  if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "backend healthy:"
    curl -s http://127.0.0.1:8000/health
    echo
    exit 0
  fi
  sleep 1
done
echo "backend did NOT come up; last log lines:"
tail -20 /tmp/panel_api.log
exit 1
