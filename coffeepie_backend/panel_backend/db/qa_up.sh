#!/usr/bin/env bash
# QA bring-up: fresh Postgres container + schema + seed + QA auth.
set -euo pipefail
cd "$(dirname "$0")/.."

docker rm -f coffeepie-panel-db >/dev/null 2>&1 || true
docker run -d --name coffeepie-panel-db \
  -e POSTGRES_PASSWORD=coffeepie_dev -e POSTGRES_DB=coffeepie -e POSTGRES_USER=coffeepie \
  -p 127.0.0.1:5432:5432 postgres:16-alpine >/dev/null

echo "waiting for postgres..."
for _ in $(seq 1 30); do
  docker exec coffeepie-panel-db pg_isready -U coffeepie -d coffeepie >/dev/null 2>&1 && break
  sleep 1
done

for f in 01_schema.sql 02_seed.sql 03_qa_auth.sql; do
  docker cp "db/$f" "coffeepie-panel-db:/tmp/$f"
  docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie -q -v ON_ERROR_STOP=1 -f "/tmp/$f" >/dev/null
  echo "[applied $f]"
done

echo "=== QA users with credentials ==="
docker exec coffeepie-panel-db psql -U coffeepie -d coffeepie -c \
  "SELECT u.email, array_agg(r.role ORDER BY r.role) AS roles
   FROM app_user u
   JOIN qa_credential c ON c.user_id = u.id
   JOIN user_role r ON r.user_id = u.id
   GROUP BY u.email ORDER BY u.email;"
