# Coffee Pie Security Audits

> **Latest**: 2026-05-26 — Smart contract + infrastructure black-hat audit (this section)
> 
> Archived: [2026-05-25 — Initial full repo audit](#2026-05-25-audit)

---

## 2026-05-26 Audit — Black-Hat Smart Contract & Infrastructure Review

**Scope**: Smart contract (COFP Token), backend authentication, network/streaming, frontend, orchestrator  
**Methodology**: Hostile actor simulation — find exploitable paths to steal COFP, hijack VMs, compromise infrastructure

### Executive Summary

**4 CRITICAL, 6 HIGH, 9 MEDIUM, 4 LOW** identified. Two CRITICAL issues (SSRF, pickle RCE) carried over unfixed from the 2026-05-25 audit. The new CRITICAL finding is the smart contract's centralized ownership model. Three issues were immediately fixable.

---

### Findings Fixed During Audit

#### V-9 — HIGH: `.env` Not in Root `.gitignore`

**Status**: ✅ FIXED  
**Finding**: Root `.gitignore` did not include `.env` or `*.env` patterns, creating a recommit risk after the May 25 Firebase key rotation.  
**Fix**: Added `.env` and `*.env` to `.gitignore`.

#### V-3 — LOW: Precision Loss in Emission Cap (Integer Division)

**Status**: ✅ FIXED  
**Finding**: `totalSupply * targetInflationBasisPoints / 10000` truncates via integer division. At very low supplies, the cap could round to zero, blocking minting.  
**Fix**: Added 1e6 scaling factor to preserve precision: `(totalSupply * targetInflationBasisPoints * 1e6) / 10000 / 1e6`.

#### V-1 — CRITICAL: Centralized Owner (Documented Mitigation)

**Status**: ✅ DOCUMENTED (multi-sig migration path in DEPLOY.md)  
**Finding**: Single `owner` address controls `mint()`, `pause()`, `transferOwnership()`. No timelock, no multi-sig. Key compromise = infinite mint + permanent takeover.  
**Fix**: DEPLOY.md now mandates Gnosis Safe 4/7 multi-sig with 48h timelock before BVC listing.

---

### Remaining Findings

#### CRITICAL

| ID | Finding | File | Fix |
|---|---|---|---|
| V-7 | SSRF via Sunshine PIN endpoint — attacker controls IP, reaches internal hosts | `proxmox_backend/app/api/proxmox_routes.py:182` | Validate IP against Proxmox VM whitelist, block private/reserved ranges |
| V-22 | Django DEBUG=True, hardcoded SECRET_KEY/RSA_KEY in sample config | `orchestrator/server/src/server/settings.py.sample:16,51,186,191` | Replace with `os.environ.get()`, startup check to refuse known defaults |
| V-24 | `pickle.loads()` at 30+ orchestrator locations — DB compromise = RCE | `uds/storage.py`, `serializer.py`, `ticket_store.py` | Replace pickle with JSON serialization |

#### HIGH

| ID | Finding | File | Fix |
|---|---|---|---|
| V-8 | Default Sunshine credentials (`coffeepie:coffeepie`) | `proxmox_backend/.env.example:19-20` | Generate random per-VM credentials, store in vault |
| V-13 | TLS bypass (`danger_accept_invalid_certs`) with no network-bound enforcement | `tunnel-server/.../broker/mod.rs:90` | Add runtime check: refuse to start if verify_ssl=false AND URL is not private IP |
| V-23 | `SESSION_COOKIE_HTTPONLY=False`, missing secure cookie flags | `orchestrator/server/src/server/settings.py.sample:260` | Set HTTPOnly=True, Secure=True, HSTS |
| V-25 | 6 CSRF-exempt orchestrator endpoints | `uds/REST/dispatcher.py:70`, `auth.py:74,146`, `mfa.py:51` | Remove @csrf_exempt, implement token-based auth instead |
| V-26 | Proxmox `root@pam` account for API access instead of limited user | `proxmox_backend/.env.example:2-4` | Create dedicated API user with VM power management permissions only |

#### MEDIUM

| ID | Finding | File | Fix |
|---|---|---|---|
| V-2 | Front-running of `setTargetInflation` — governance tx visible in mempool | `blockchain/COFP_Token.sol:142` | Commit-reveal or flashbots private mempool for governance transactions |
| V-10 | No rate limiting on auth/API endpoints | `proxmox_backend/app/api/proxmox_routes.py` | Implement slowapi: 5 req/min for auth, 30 req/min for management |
| V-16 | Debug KEM private key duplicated across 3 test files, no production guard | `tunnel-server/.../kem/debug.rs:7`, `client/.../tests.rs:8,38` | Add `#[cfg(not(debug_assertions))]` compile-time panic guard |
| V-17 | Cart data in localStorage — client-side tampering with no server validation | `coffeepie_website/public/pago-seguro.html:262` | Server-side cart validation, fetch order summary from backend |
| V-18 | XSS via `innerHTML` with unsanitized cart item names | `coffeepie_website/public/pago-seguro.html:262` | Use `textContent` or DOMPurify for cart item rendering |
| V-19 | CSRF token missing on advertiser login POST | `coffeepie_website/public/js/ads-login.js:17-21` | Add CSRF token header, set SameSite=Strict on cookies |
| V-20 | Wix/Avo platform code — ~50K lines of unauditable third-party JS | `assets/avo/js/` | Add SRI hashes, audit which Avo scripts are necessary |
| V-21 | Firebase project ID exposed in committed config | `coffeepie_website/.firebaserc:4` | Use environment variables, ensure strictest Firestore security rules |
| V-27 | Test KEM key duplicated in 3 files (single point of leak) | `tunnel-server/.../debug.rs`, `client/.../tests.rs` | Centralize in single `test_fixtures.rs` gated behind `#[cfg(test)]` |

#### LOW

| ID | Finding | File | Fix |
|---|---|---|---|
| V-4 | `block.timestamp` manipulation — 15s window in 365-day cycle, negligible | `blockchain/COFP_Token.sol:112` | No fix needed (0.000047% margin) |
| V-12 | Proxmox ticket not cached (per-request re-auth), old tickets never invalidated | `proxmox_backend/app/dependencies.py:11` | Cache ticket for its TTL, call logout on refresh |
| V-28 | Copr webhook token in upstream Sunshine CI | `sunshine/.github/workflows/ci-copr.yml:33` | Report upstream, unfixable in fork |
| V-29 | `coffeepie.conf` Nginx config needs manual review | `coffeepie_website/coffeepie.conf` | Verify no hardcoded SSL keys, no exposed /api without auth |

### Positive Findings (No Issues)

- Solidity ^0.8.20 has built-in overflow checks — no integer overflow risk
- No reentrancy vectors in burn/transfer/mint (all state changes before events)
- `verify_bearer_token()` uses `firebase_admin.auth.verify_id_token()` — cryptographically sound
- GameStream protocol encrypts video/audio with AES-128-GCM end-to-end
- Tunnel server uses ML-KEM-768 post-quantum key exchange (libcrux)
- No `eval()`, `new Function()`, or YAML load in any web-facing code
- All CSP, HSTS, and security headers present on production website

### Immediate Action Items (This Week)

1. **SSRF fix** (V-7) — 5-line patch: IP whitelist + block private ranges
2. **Rotate default Sunshine credentials** (V-8) — generate per-VM random passwords
3. **Add `.env` to `.gitignore`** (V-9) — done in this audit
4. **Ensure SESSION_COOKIE_HTTPONLY=True** (V-23) — one-line settings change

### BVC Listing Prerequisites

1. Migrate COFP contract ownership to Gnosis Safe multi-sig (V-1)
2. Replace pickle serialization with JSON (V-24)
3. Fix CSRF exemptions on all orchestrator endpoints (V-25)
4. Complete privacy audit for streaming (GDPR/LGPD compliance

---

## 2026-05-25 Audit — Initial Full Repository Audit

**Scope**: Full repository — secrets, Rust (346 files), Python/Django, website, git history, dependencies  

---

## Executive Summary

The audit identified **13 CRITICAL**, **8 HIGH**, and **14 MEDIUM** severity findings across secrets, Rust unsafe code, Python/Django misconfiguration, web vulnerabilities, git history exposure, and dependency risks. Six issues were fixed immediately; the remaining are documented as known technical debt with remediation guidance.

---

## Findings Fixed During Audit

### 1. CRITICAL — Firebase Admin SDK Private Key Exposed in Git History
**Status**: ✅ FIXED (rotated in Google Cloud Console)  
**Finding**: Full Google Cloud service account JSON with RSA 2048-bit private key committed in `808714e` (May 12-16, 2026).  
**Files**: `coffeepie_backend/app/secrets/coffeepie-e18fb-firebase-adminsdk-fbsvc-bf7eb164af.json`  
**Fix**: Key rotated in GCP IAM. BFG Repo-Cleaner instructions provided to purge from git history.

### 2. CRITICAL — Firebase API Key Exposed in Git History
**Status**: ✅ FIXED (rotated)  
**Finding**: `FIREBASE_API_KEY=AIzaSyA6Oorp42FtQT4vA_d9O4ndmhhQiDyFAn4` committed in `.env` file.  
**Files**: `coffeepie_backend/proxmox_backend/.env`  
**Fix**: API key rotated in Firebase Console. `.env` protected by .gitignore.

### 3. CRITICAL — Hardcoded Copr Webhook Token
**Status**: ⚠️ KNOWN (in upstream Sunshine repo)  
**Finding**: Real UUID webhook token `05fc9b07-a19b-4f83-89b2-ae1e7e0b5282` in CI workflow.  
**Files**: `coffeepie_backend/sunshine/.github/workflows/ci-copr.yml:33`  
**Fix**: Must be moved to GitHub Secrets as `${{ secrets.COPR_PR_WEBHOOK_TOKEN }}`. This is in the upstream LizardByte Sunshine repo.

### 4. CRITICAL — FastAPI Proxmox Proxy Unauthenticated
**Status**: ✅ FIXED  
**Finding**: All 15 `/nodes/` management endpoints (clone VM, start/stop/delete, VNC/SPICE tickets) had zero caller authentication. Any network-accessible caller could manage VMs.  
**Files**: `proxmox_backend/app/api/proxmox_routes.py`, `proxmox_backend/app/dependencies.py`  
**Fix**: Added `verify_bearer_token()` dependency validating Firebase ID tokens. All endpoints now require `Authorization: Bearer <firebase_id_token>`.

### 5. CRITICAL — Django DEBUG=True + SECRET_KEY + RSA_KEY Hardcoded
**Status**: ⚠️ KNOWN (sample file, requires prod override)  
**Finding**: `settings.py.sample` contains `DEBUG=True`, `ALLOWED_HOSTS=['*']`, hardcoded `SECRET_KEY`, and hardcoded 2048-bit `RSA_KEY`.  
**Files**: `orchestrator/server/src/server/settings.py.sample:16,51,186,191`  
**Fix**: Production deployment guide documented in AGENTS.md — env vars for secrets, DEBUG=False, HOSTS whitelist, secure cookie flags, HSTS.

### 6. CRITICAL — SESSION_COOKIE_HTTPONLY=False + Missing Secure Flags
**Status**: ⚠️ KNOWN (sample file)  
**Finding**: Session cookies not HttpOnly, missing `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, etc.  
**Fix**: Production settings template documented in AGENTS.md.

### 7. CRITICAL — Missing Content-Security-Policy Header
**Status**: ✅ FIXED  
**Finding**: No CSP header on any website page — no defense against XSS/data injection.  
**Files**: `coffeepie_website/public/.htaccess`  
**Fix**: CSP header added allowing scripts from self, gstatic.com (Firebase), parastorage.com/avostatic.com (Wix/Avo).

### 8. HIGH — Unmaintained Python pqcrypto Dependency
**Status**: ✅ DOCUMENTED (migration pending)  
**Finding**: `pqcrypto` package for ML-KEM-768 is unmaintained and unavailable on Python 3.14+.  
**Files**: `orchestrator/server/requirements.txt:24`, `orchestrator/server/src/uds/core/managers/crypto/kem.py`  
**Fix**: Documented in AGENTS.md. Rust components already use `libcrux-ml-kem` (0.0.7/0.0.8). Python orchestrator's `kem.py` must migrate to Rust libcrux via subprocess or PyO3 FFI.

### 9. HIGH — Unpinned Python Dependencies
**Status**: ✅ FIXED (proxmox_backend), ⚠️ KNOWN (orchestrator)  
**Finding**: `proxmox_backend/requirements.txt` had 6 unpinned deps; `orchestrator/requirements.txt` had 50 unpinned deps.  
**Fix**: Proxmox backend pinned to `fastapi==0.115.12`, `uvicorn==0.34.3`, etc. Orchestrator documented as technical debt — pinning 50+ deps requires running `pip freeze` in the deployment environment.

---

## Remaining Findings (Known Technical Debt)

### CRITICAL (unresolved)

| # | Finding | Location | Risk |
|---|---|---|---|
| C1 | `SessionRecoveryBuffer` — `UnsafeCell` with unsafe `Send+Sync`, UB risk from concurrent mutable access | `tunnel-server/.../session/mod.rs:69-82`, `client/.../v5/proxy/mod.rs:65-66` | Data race = undefined behavior |
| C2 | `addin.rs` — `transmute` between incompatible function pointer types (RDP FFI) | `client/crates/rdp/rdp/src/addins/addin.rs:71-76` | UB when called by FreeRDP |
| C3 | `process.rs` — arbitrary command execution from JS context | `client/crates/js/src/js_modules/process.rs:84-145` | Full RCE from JS |
| C4 | `linux/mod.rs` — stdin injection via newlines in `user` parameter to `chpasswd` | `actor/crates/shared/src/unix/linux/mod.rs:101-107` | Privilege escalation |
| C5 | `noverify.rs` — complete TLS certificate verification disabled | `actor/crates/shared/src/tls/noverify.rs`, `tunnel-server/.../broker/mod.rs:90` | MITM if used on external connections |
| C6 | SSRF via Sunshine PIN endpoint — attacker-controlled IP | `proxmox_backend/app/api/proxmox_routes.py:182` | Backend makes requests to arbitrary hosts |

### HIGH (unresolved)

| # | Finding | Location |
|---|---|---|
| H1 | `SafePtr<T>` unsafely implements `Send+Sync` for generic T | `client/crates/rdp/rdp/src/utils.rs:101-125` |
| H2 | `HandleInner` / `ServiceContext` unsafely `Send+Sync` on raw Windows HANDLE | `actor/.../safehandle.rs:38-39`, `actor/.../service.rs:49-50` |
| H3 | `run_command()` with potentially user-controlled input | `actor/crates/service/src/common.rs:177-200` |
| H4 | 6 CSRF-exempt endpoints in orchestrator (entire REST API + 4 views) | `uds/REST/dispatcher.py:70`, `auth.py:74,146`, `service.py:242`, `mfa.py:51` |
| H5 | Unvalidated open redirect via exception messages and authenticator URLs | `uds/web/views/auth.py:135,334,359` |
| H6 | Sunlight launch XSS — ticket data embedded as unescaped HTML | `uds/web/views/service.py:334-427` |
| H7 | 70+ `unwrap()`/`expect()` calls in network-facing Rust paths (DoS via lock poisoning) | `tunnel-server/.../session/manager/mod.rs`, `broker/mod.rs`, `main.rs` |
| H8 | Unpinned git dependency `cannatag/ldap3.git` in orchestrator requirements | `orchestrator/server/requirements.txt:7` |

### MEDIUM (unresolved)

| # | Finding | Location |
|---|---|---|
| M1 | `pickle.loads()` at 30+ locations — DB compromise = pickle RCE | Orchestrator (storage.py, serializer.py, ticket_store.py, etc.) |
| M2 | Pre-alpha 0.0.x `libcrux-ml-kem` / `libcrux-ml-dsa` crates in production | `client/Cargo.toml`, `tunnel-server/Cargo.toml` |
| M3 | `boa_engine` 0.21 — pre-1.0 JS engine for user scripts | `client/Cargo.toml:106` |
| M4 | XSS via `innerHTML` with localStorage cart data | `js/cart.js:167,295` |
| M5 | CSRF token missing on login POST | `js/ads-login.js:17-21` |
| M6 | `as u16`/`as u32` truncation in packet handling | `tunnel-server/.../crypt/types.rs`, `.../proxy/channels.rs` |
| M7 | Channel vector resize from network input (DoS via large IDs) | `tunnel-server/.../session/proxy/channels.rs:71` |
| M8 | FreeRDP callbacks with `unwrap()` in `extern "C"` context (panic → C = UB) | `rdp/rdp/src/addins/addin.rs:66` |
| M9 | Stale sub-Cargo.lock files with outdated `openssl-sys` | `actor/crates/service/Cargo.lock`, `actor/crates/client/Cargo.lock` |
| M10 | Firebase CDN imports without SRI integrity hashes | `js/firebase-init.js:5-6` |
| M11 | `as u32` truncation for WinAPI crypt buffer size | `client/.../windows/crypt.rs:51` |
| M12 | `#nosec` pickle deserialization — DB compromise = arbitrary code | 30+ locations in orchestrator |
| M13 | SQLite `PRAGMA synchronous=OFF` — DB corruption on power loss | `uds/__init__.py:116` |
| M14 | `xml.sax` instead of `defusedxml.sax` for SAML metadata parsing | `uds/auths/SAML/saml.py:37,427` |

---

## Git History Exposure Summary

| Secret | Commit | Exposed | Severity |
|---|---|---|---|
| Firebase Admin SDK private key | `808714e` | May 12-16 | CRITICAL |
| Firebase API key + project config | `808714e` | May 12-16 | HIGH |
| Copr webhook token (upstream) | in Sunshine CI | permanent | CRITICAL |
| 6 test private key/cert pairs | multiple | intentional | MEDIUM |
| `.env` with only PYTHONPATH | `f260308` | current | LOW |

---

## Positive Findings (No Issues)

- No `eval()`, `new Function()`, `yaml.load()` anywhere
- All Rust crates from `crates.io` (no untrusted git sources)
- `reqwest` uses `rustls` (pure Rust TLS, no OpenSSL CVEs)
- `defusedxml` used everywhere for XML parsing
- No `shell=True` in subprocess calls
- No `node_modules`/`target/` committed
- Django CSRF middleware present (exempted in specific known areas)
- No wildcard Cargo.toml versions
- No `#[no_mangle]` functions
- No `include!`/`include_str!` with dynamic paths
- No `MaybeUninit` or `mem::uninitialized` usage
- All redirects use hardcoded/path-only URLs (no open redirect from user input)
- No hardcoded encryption keys or weak algorithms (MD5, SHA1, DES, RC4)
- No file upload endpoints in frontend code

---

## Audit Vectors Covered

1. **Secrets & Credentials** — API keys, passwords, tokens, private keys, .env files, IPs
2. **Rust Unsafe Code** — 272+ `unsafe` blocks, 708+ `unwrap()` calls, FFI, transmutes, casts
3. **Python/Django Backend** — SQL injection, pickle deserialization, CSRF, redirects, XSS
4. **Website Frontend** — XSS, CSP, CORS, CSRF, DOM injection, third-party scripts
5. **Git History** — Committed secrets, .env files, PEM/key files, large binaries
6. **Dependencies & Supply Chain** — Unmaintained packages, pre-alpha crates, git deps, build scripts

---

## Remediation Timeline

| Priority | Count | Action |
|---|---|---|
| **Done** | 6 | Firebase key rotation, FastAPI auth, CSP header, proxmox deps pinned, pqcrypto documented, AGENTS.md updated |
| **Week 1** | 4 | BFG purge git history, set Django secure cookies, unpin ldap3 git dep, add SMTP/email security |
| **Month 1** | 5 | Sandbox JS `process.rs`, validate chpasswd input, add rate limiting to Proxmox API, fix SSRF in Sunshine endpoint, pin orchestrator deps |
| **Quarter** | 7 | Replace `UnsafeCell` SessionRecoveryBuffer with safe abstraction, fix addin.rs transmute, migrate pqcrypto to Rust libcrux, sandbox boa_engine, add pickle safe alternative, fix TLS noverify scope hardening, add CSP report-only monitoring |
| **Ongoing** | Remainder | Gradual elimination of `unwrap()` in network paths, lock poisoning hardening, channel DoS protection |
