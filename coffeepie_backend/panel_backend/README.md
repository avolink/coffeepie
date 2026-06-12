# Coffee Pie Panel Backend

Backend for `coffeepie_website/public/panel.html` — the role-based dashboard for
Advertisers, Manufacturers, Providers, and Contributors.

The panel today is **100% static mock data** (no `fetch()` calls). This service
provides the missing pieces; the rest of the economy was already built elsewhere
in the repo and should be reused, not duplicated.

## What already exists (reuse — do not rebuild)

| Concern | Where |
|---|---|
| Login / 2FA / user identity | `proxmox_backend/app/services/auth_service.py` (Firebase) |
| Fiat payments (PSE, Bre-B, Bancolombia), DIAN invoices, COFP↔COP↔Cr math | `coffeepie_backend/payments/` |
| COFP token (ERC-20: mint/burn/transfer/pause) | `blockchain/COFP_Token.sol` |
| Slice capacity, VM lifecycle, placement | `coffeepie_orchestrator/dc-agent/` |

## What THIS service adds

1. **RBAC over a provider-agnostic identity layer** (`app/auth/`) — the four panel
   roles with a `require_roles(...)` dependency. Identity sits behind an
   `IdentityProvider` interface with **Supabase** (production — JWT verified via
   JWKS or shared secret, roles in `app_metadata.roles`) and **Firebase**
   (prototype) implementations, selected by `AUTH_PROVIDER`. Default `both` runs
   the Composite provider that accepts either token — the roadmap's
   Firebase→Supabase migration window. Per AGENTS.md, Supabase is the sovereign,
   self-hostable, PostgreSQL-aligned target. Roles did not exist anywhere before.

2. **Registration anti-bot gate** (roadmap — T-507). The `/auth/register` endpoint
   currently creates accounts immediately (QA-local only, gated by
   `QA_LOCAL_AUTH=***. The production registration flow will add:

   | Layer | Mechanism |
   |---|---|
   | Rate limiting | Per-IP: max 3 registrations per 15 min. DB-backed `qa_rate_limit` table so it survives restarts. |
   | Verification token | Registration creates account in `unverified` state. A random 32-byte token (24h expiry) is stored in `qa_verification` and sent via email. |
   | Login gate | `/auth/login` rejects accounts with `email_verified = FALSE`. |
   | Verify endpoint | `GET /auth/verify-email?token=...` activates the account and redirects to login. |
   | Email transport | `smtplib` via env vars (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`). Falls back to stdout logging when unconfigured (QA). |
   | Frontend UX | After registration, modal shows "Revisa tu correo para verificar tu cuenta" instead of redirecting. |

   The Supabase production path already has email verification built in — this
   implementation mirrors the same contract so the frontend works identically in
   both environments. See ROADMAP.json M5 T-507.

3. **COFP metering** (`app/cofp/metering.py`) — the rule **1 COFP = 1 slice·minute
   *effectively served***. Idle/booted-but-unused VM time mints nothing.
4. **COFP ledger** (`app/cofp/ledger.py`) — off-chain source of truth: accrual to
   Providers, balances, Contributor voting power, burn-on-withdrawal with
   tier-adjusted fiat quotes. Storage is behind a `LedgerRepository` Protocol
   (in-memory impl for now).
5. **Role-gated routes** (`app/api/cofp_routes.py`) — usage ingest, balance,
   provider summary, governance voting power, withdraw.

Pure logic is covered by tests:
```
PYTHONPATH=. python -m unittest tests.test_metering tests.test_ledger
```
(14 tests, no Firebase/network needed.)

## Architecture: how a slice·minute becomes a COFP

```
Sunshine session (frames delivered)
  └─ emits start/stop  ──►  DC Agent  ──►  POST /cofp/usage {slices, seconds, streaming}
                                              └─ ledger.accrue_for_usage()  ──►  +COFP to Provider
Provider clicks "Retirar" ──► POST /cofp/withdraw ──► ledger burn entry + fiat quote
                                              └─ settlement worker ──► bank payout + on-chain burnFrom
```

---

## What I need from the backend partner

The pure economic core is done and tested. These are the integrations only your
partner can own, roughly in priority order:

1. **Durable `LedgerRepository` on Supabase Postgres.** The in-memory repo resets
   on restart. The COFP ledger is money — it needs ACID storage, and the accrual
   ingest needs a **dedup key on `(instance_id, window)`** so DC-Agent retries
   can't double-mint. Use the same Supabase Postgres as IAM (sovereign,
   self-hostable) and enforce per-account access with **Row-Level Security**.
   *This is the #1 blocker.*

   Note: the `firebase_admin` dependency is only needed while `AUTH_PROVIDER` is
   `both` or `firebase`. Once cut over to Supabase, drop it from requirements.

2. **The usage feed from the streaming layer.** Metering needs per-session
   `streaming` truth — when a Moonlight client is actually connected and
   receiving frames, not just "VM is on". Today the DC-Agent's `CapacityReport`
   only knows VMs exist. Partner work: emit session start/stop (with slice count
   and duration) from the Sunshine lifecycle → DC-Agent → `POST /cofp/usage`.

3. **Settlement worker (fiat payout + on-chain burn).** `/cofp/withdraw` records
   the burn and quotes COP but deliberately does **not** move money. A worker must
   consume `WITHDRAWAL` entries and (a) initiate a bank **payout/dispersión** and
   (b) call `burnFrom` on `COFP_Token`. ⚠️ The existing `payments/` backends are
   pay-**in** only; outbound payout is a different Bre-B/bank API the partner must
   add. Needs a chain signer (KMS-held key) for the mint/burn settlement.

4. **Per-tab CRUD + DB schema.** Campaigns, Segments, Assets, Reports, API Keys,
   Licenses, and Node-registry persistence are not implemented — they're
   straightforward once the DB is chosen. Each maps to a panel tab; models should
   mirror the field names already in `panel.html`. The node-registry endpoint
   should reuse the DC-Agent (`POST /instances`, `/capacity`) rather than a new
   path.

5. **Set roles on onboarding.** Call `firebase_auth.set_user_roles(uid, [...])`
   when a user is approved as Provider, onboarded as Advertiser, etc. Decide the
   approval flow (self-serve vs. manual review) — Providers and fiat withdrawal
   especially.

## ⚠️ Compliance flags (business/legal, not code)

- **COFP burned → fiat bank transfer** is a money-out flow. In most jurisdictions
  that implicates **money-transmitter / KYC / AML** obligations. The withdraw path
  must gate on verified identity before any payout. Don't ship this without legal
  sign-off.
- **"Token for voting power"** can be treated as a **security** depending on how
  it's marketed and whether holders expect profit. Get this reviewed.
- COFP↔fiat at a published rate makes COFP look like a **stablecoin/e-money**;
  pricing via "governance oracle" doesn't remove that. Same review applies.

These are not blockers for building, but they are blockers for *operating* the
withdrawal feature.
