#!/usr/bin/env bash
# Start the panel backend against the real Supabase project (not the QA-local
# Postgres). Reads DATABASE_URL / SUPABASE_URL / SUPABASE_JWT_SECRET /
# NODE_CRED_ENC_KEY from the environment or panel_backend/.env (python-dotenv,
# loaded by app/config.py) — this script sets no secrets itself and refuses to
# start with QA defaults, so a misconfigured shell can't quietly write real
# rows with a throwaway key.
set -uo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a; source .env; set +a
fi

missing=()
[ -z "${DATABASE_URL:-}" ] && missing+=(DATABASE_URL)
[ -z "${SUPABASE_URL:-}" ] && missing+=(SUPABASE_URL)
[ -z "${NODE_CRED_ENC_KEY:-}" ] && missing+=(NODE_CRED_ENC_KEY)
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing required env var(s): ${missing[*]}"
  echo "Set them in panel_backend/.env or export them before running this script."
  exit 1
fi
if [ "${NODE_CRED_ENC_KEY}" = "ZVqh3DooH0vtHasv_SRjBQH3wJ0I9pDZYWNglQg2qJE=" ]; then
  echo "NODE_CRED_ENC_KEY is the QA-only default — refusing to run against Supabase with it."
  echo "Generate a real one: python3 -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
  exit 1
fi

pkill -f "uvicorn app.main" 2>/dev/null || true
sleep 1

export PYTHONPATH=.qa_libs:.
export QA_LOCAL_AUTH=false
export AUTH_PROVIDER=supabase
export PANEL_DB_DRIVER=${PANEL_DB_DRIVER:-pg8000}
export LEDGER_BACKEND=postgres

nohup python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/panel_api_supabase.log 2>&1 &
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
tail -20 /tmp/panel_api_supabase.log
exit 1
