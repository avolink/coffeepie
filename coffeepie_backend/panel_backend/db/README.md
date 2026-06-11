# Panel QA Test Database

A self-contained PostgreSQL 16 database for QA-testing the panel against the live
prototype. Schema mirrors `panel_backend` (RBAC, COFP ledger, node registry) and
ports cleanly to Supabase.

Files:
- `01_schema.sql` — tables, enums, the `account_balance` view, dedup constraint.
- `02_seed.sql` — QA fixtures (one user per role, ledger entries, nodes).
- `99_qa_checks.sql` — verification queries (not run on deploy).
- `docker-compose.yml` — Postgres bound to **loopback only**.

All of the above is **validated** against a real `postgres:16-alpine`: schema +
seed apply, seed is idempotent, balances derive correctly (provider = 240 COFP,
contributor = 500), and the dedup constraint blocks double-mint.

## Deploy (on the Proxmox / Endpoints VM)

```bash
cd coffeepie_backend/panel_backend
cp .env.example .env            # set POSTGRES_PASSWORD to a real value
docker compose -f db/docker-compose.yml up -d
# verify:
docker exec -i coffeepie-panel-db psql -U coffeepie -d coffeepie -f /dev/stdin < db/99_qa_checks.sql
```

The backend then connects with:
```
postgresql://coffeepie:<password>@127.0.0.1:5432/coffeepie
```

## 🔒 Security — read before deploying on the Endpoints VM

The Endpoints VM already exposes an API publicly (`:8080`). The database MUST NOT
join it on the public interface:

1. **Loopback binding is mandatory.** `docker-compose.yml` publishes the port as
   `127.0.0.1:5432:5432`. Do **not** change it to `5432:5432` — that binds
   `0.0.0.0` and exposes every user credential to the internet. The backend
   reaches Postgres over localhost; nothing external should.
2. **Firewall stays minimal.** On that VM the public firewall should allow only
   443 (the API over HTTPS). 5432 must never be open to the internet.
3. **The website server never gets DB credentials.** It serves static files only.
   Only the backend API holds the connection string and talks to Postgres. This
   is why the three tiers (static site → backend API → DB) stay separate: it
   keeps credentials and direct DB access off the public-facing box.
4. **This is a TEST DB.** The seed passwords/keys are throwaway. Do not point it
   at, or copy it into, anything holding real user data.

## QA test users (from seed)

| Email | Role(s) | Notes |
|---|---|---|
| advertiser@qa.coffeepie.co | advertiser | campaigns/segments/assets |
| manufacturer@qa.coffeepie.co | manufacturer | QFDM licenses |
| provider@qa.coffeepie.co | provider | owns 2 nodes, balance 240 COFP |
| contributor@qa.coffeepie.co | contributor | balance 500 COFP (voting power) |
| admin@qa.coffeepie.co | admin | passes all role gates |
| prosumer@qa.coffeepie.co | provider + advertiser | multi-role |

To exercise RBAC end-to-end you still need tokens carrying these roles. With
`AUTH_PROVIDER` pointed at a QA Supabase project, set each user's
`app_metadata.roles` to match the table above (service-role key). The `account_id`
in the ledger is the IdP `sub`/uid — for QA the seed uses the `app_user.id`
UUIDs; map your Supabase user ids to those, or update the seed to your QA uids.
