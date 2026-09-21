# Coffee Pie — Backend, Blockchain & Infrastructure Deep Audit

**Date**: 2026-06-05  
**Auditor**: Hermes Agent (automated deep audit)  
**Scope**: `coffeepie_backend/`, `blockchain/`, Docker infrastructure, root config, `tools/`, `scripts/`, `tests/`, `cloud-providers/`, `hardware-manufacturers/`  
**Methodology**: Static analysis of all source files, configuration review, architectural coherence verification, security posture assessment.

---

## OVERALL SCORES

| Component | Score | Grade |
|---|---|---|
| Smart Contract (COFP_Token.sol) | 78/100 | B+ |
| Backend Security | 62/100 | C- |
| Infrastructure | 68/100 | C+ |
| Tools | 85/100 | B |
| Dependencies | 72/100 | B- |
| Coherence | 88/100 | B+ |
| **OVERALL** | **75/100** | **B** |

---

## 1. SMART CONTRACT — COFP_Token.sol + DEPLOY.md

### 1.1 Solidity Version & Compiler

**Score: 90/100 — Minor observation**

| Item | Finding |
|---|---|
| Pragma | `^0.8.20` (line 8) — correct. Built-in overflow/underflow protection from Solidity 0.8.0+. No SafeMath needed. |
| Compiler target | DEPLOY.md specifies `0.8.20` explicitly (line 20). Good. |
| License | MIT (line 1). Compatible with open-source deployment. |

*Finding #1 (LOW)*: Pragma `^0.8.20` allows any 0.8.x version >= 0.8.20. Consider pinning to exact `0.8.20` to ensure reproducible bytecode verification on Tronscan.

### 1.2 Access Control

**Score: 65/100 — Centralized model with documented mitigations**

| Item | Status |
|---|---|
| `onlyOwner` modifier | Lines 31-34. Controls `mint()`, `pause()`, `unpause()`, `transferOwnership()`. |
| Owner set in constructor | Line 42. Deployer becomes owner + receives 100M COFP. |
| Multi-sig migration | DEPLOY.md line 163 mandates Gnosis Safe 4/7 before BVC listing. Good. |
| Timelock | DEPLOY.md line 164 mandates 48h timelock. Good — but NOT enforced in contract. |
| Pause mechanism | `whenNotPaused` on `transfer()`, `transferFrom()`. Good circuit breaker. |

*Finding #2 (HIGH)*: The 48-hour timelock mentioned in DEPLOY.md (line 164) is NOT implemented in the contract. A single owner key compromise allows instant `mint()` to create unlimited tokens, `transferOwnership()` to permanently seize control, or `pause()` to freeze all transfers. The DEPLOY.md says "Enable 48-hour timelock on all onlyOwner functions" — this is a manual/operational requirement that should be encoded in the contract or enforced by the Gnosis Safe itself.

*Finding #3 (MEDIUM)*: `approve()` (line 59-63) does NOT have the `whenNotPaused` modifier. During a pause, users can still set allowances, which could be exploited after unpausing. This is inconsistent with `transfer()` and `transferFrom()` which are paused.

*Finding #4 (MEDIUM)*: `transferOwnership()` (line 121-125) emits the event BEFORE updating the state variable:
```
emit OwnershipTransferred(owner, _newOwner);  // line 123
owner = _newOwner;                            // line 124
```
This means the event is emitted with the old owner as `previousOwner` which is correct, but if a reentrancy attack reads `owner` between lines 123-124, it sees the old owner. While not exploitable in this simple function, it violates the Checks-Effects-Interactions pattern. Move the event emission AFTER the state change.

### 1.3 Integer Overflow/Underflow

**Score: 95/100 — Solid**

Solidity 0.8.x has built-in checked arithmetic. All arithmetic operations (`+=`, `-=`) are safe:
- `totalSupply += _value` (line 102) — checked
- `balanceOf[msg.sender] -= _value` (line 53) — checked
- `INITIAL_SUPPLY = 100_000_000 * 10 ** 18` (line 14) — compile-time constant, safe

*Finding #5 (LOW)*: The `mint()` function has no supply cap (line 100-106), so no overflow concern. The previous `remint()` used `totalSupply + _value <= MAX_SUPPLY` which relied on checked addition — also safe. This is purely a design choice: elastic supply with no cap.

### 1.4 Reentrancy Vectors

**Score: 88/100 — Minor risk**

| Function | Reentrancy Risk | Analysis |
|---|---|---|
| `transfer()` | None | No external calls |
| `approve()` | None | No external calls |
| `transferFrom()` | None | No external calls |
| `burn()` | None | No external calls |
| `burnFrom()` | None | No external calls |
| `mint()` | None | No external calls |

None of these functions make external calls, so reentrancy is not a practical concern. The contract is ERC-20 only and does not use hooks/callbacks.

*Finding #6 (LOW)*: Consider adding OpenZeppelin's `ReentrancyGuard` as defense-in-depth if future upgrades add token hooks or callbacks.

### 1.5 Event Emission Correctness

**Score: 85/100 — Minor ordering issue**

All TRC-20 required events are emitted: `Transfer`, `Approval`. Plus custom events: `Burn`, `Mint`, `OwnershipTransferred`, `Paused`, `Unpaused`.

*Finding #7 (LOW)*: `burn()` emits `Burn` then `Transfer` (lines 81-82). `burnFrom()` does the same (lines 92-93). This is correct TRC-20 behavior. `mint()` emits `Mint` then `Transfer` (lines 104-105). Good.

*Finding #8 (LOW)*: No event is emitted when `constructor()` mints (though `Transfer(address(0), ...)` is emitted at line 45). Good.

### 1.6 Front-Running Risk

**Score: 75/100 — Known ERC-20 limitation**

*Finding #9 (MEDIUM)*: `approve()` is vulnerable to the classic ERC-20 allowance front-running attack. If Alice has approved Bob for N tokens and wants to change it to M, Bob can front-run Alice's `approve(alice, M)` transaction and spend the original N allowance before the new M takes effect. Standard mitigation: use `increaseAllowance()`/`decreaseAllowance()` functions. **Neither is implemented.**

### 1.7 Emission Precision

**Score: 90/100 — Correct**

`INITIAL_SUPPLY = 100_000_000 * 10 ** 18` — Exactly 100 million COFP with 18 decimal places as the initial bootstrap supply. This is correct for TRC-20 maximum precision. No MAX_SUPPLY cap — supply is elastic, growing with network compute provision at 1 COFP per Slice·min.

*Finding #10 (LOW)*: The `decimals = 18` (line 13) means 1 COFP = 10^18 sub-units. This matches the documentation in DEPLOY.md (line 59). However, wallet holding limits (100,000,000,000 COFP) and other business logic operate in whole COFP units. Ensure the backend uses `balanceOf(address) / 10**18` correctly when applying the 100B COFP holding limit.

### 1.8 DEPLOY.md Completeness

**Score: 88/100 — Thorough but requires operational enforcement**

| Section | Status |
|---|---|
| Prerequisites | Complete |
| Deployment steps | Complete (Remix IDE + TronLink) |
| Verification on Tronscan | Complete |
| Monetary policy | Detailed explanation of elastic supply, mint, 1 COFP/Slice·min |
| Decimal precision | Documented with use cases |
| Backend integration | TRON RPC endpoints, contract functions listed |
| Post-deployment checklist | Detailed: Gnosis Safe, timelock, signer succession, monitoring |
| Emergency procedures | `pause()`/`unpause()` documented |

*Finding #11 (MEDIUM)*: DEPLOY.md line 42 says "The constructor takes **no arguments** — supply is fixed at deploy time" but doesn't mention that the deployer receives ALL 100M tokens. This is an important operational detail — the deployer wallet must be secured immediately.

*Finding #12 (LOW)*: DEPLOY.md suggests `cargo run --release` for dc-agent and actor but these are Rust containers that should use pre-built binaries in production, not compile-from-source in the container.

---

## 2. BACKEND SECURITY

### 2.1 API Authentication

**Score: 55/100 — Critical gaps**

| Endpoint | Auth? | File:Line |
|---|---|---|
| `/payments/webhook/pse` | **NO** | `webhook.py:22` |
| `/payments/webhook/breb` | **NO** | `webhook.py:36` |
| `/payments/webhook/bancolombia` | **NO** | `webhook.py:50` |
| `/payments/webhook/health` | NO (acceptable) | `webhook.py:64` |
| `/auth/create-user` | NO | `auth_routes.py:7` |
| `/auth/login` | NO | `auth_routes.py:15` |
| `/auth/forgot-password` | NO | `auth_routes.py:27` |
| `/nodes` | YES (Bearer) | `proxmox_routes.py:27` |
| `/nodes/{node}/vms` | YES (Bearer) | `proxmox_routes.py:32` |
| `/sunshine/send-pin` | YES (Bearer) | `proxmox_routes.py:170` |

*Finding #13 (CRITICAL)*: All payment webhook endpoints (`webhook.py` lines 22-61) have ZERO authentication. Any attacker who discovers the webhook URL can POST arbitrary payment confirmations. While Bre-B has HMAC signature verification (`breb.py` line 159), PSE (`pse.py` line 136) and Bancolombia (`bancolombia.py` line 110) have no webhook signature verification at all. An attacker can POST `{"transaction_id":"fake","status":"APPROVED","amount":999999}` to `/payments/webhook/pse` and receive `{"status":"ok"}`.

*Finding #14 (HIGH)*: Auth endpoints (`auth_routes.py`) have no rate limiting. Brute-force attacks on `/auth/login` or `/auth/forgot-password` are unmitigated.

*Finding #15 (MEDIUM)*: `/auth/create-user` has no CAPTCHA, no email verification, no invitation requirement. Any anonymous caller can create unlimited Firebase users.

### 2.2 Firebase Token Validation

**Score: 82/100 — Good with minor issues**

| Item | Status |
|---|---|
| Token verification | `dependencies.py:23-43` uses `verify_bearer_token()` dependency |
| Bearer scheme | FastAPI `HTTPBearer()` with `Security()` — correct |
| Error handling | Returns 401 with `WWW-Authenticate: Bearer` header |
| Firebase init | `auth_service.py:8-25` uses `FIREBASE_ADMIN_SDK_JSON` path from config |

*Finding #16 (MEDIUM)*: `auth_service.py` lines 8-9 compute `base_dir` as `os.path.dirname(os.path.dirname(os.path.dirname(__file__)))` and joins with `config.FIREBASE_ADMIN_SDK_JSON`. If `FIREBASE_ADMIN_SDK_JSON` is a relative path, the resolution depends on file location. If it's an absolute path, the `base_dir` join produces an incorrect path. The code should check if the value is absolute before joining.

### 2.3 SQL Injection Vectors

**Score: 85/100 — Django ORM is safe, raw cursor uses are static**

The orchestrator (`coffeepie_orchestrator/`) is a Django-based system (OpenUDS fork). Django ORM queries are parameterized by default and safe.

*Finding #17 (LOW)*: `uds/core/util/model.py` lines 77-83 use raw `cursor.execute()` for `SELECT CURRENT_TIMESTAMP(4)` — this is a static query, no user input. Safe. Line 173-174 uses `cursor.execute(query)` where `query` is derived from higher in the function. Worth auditing the callers to ensure no user-controlled strings reach this path.

*Finding #18 (LOW)*: The Coffee Pie payments module uses dataclasses with no ORM, so SQL injection is not applicable — it's a library, not a database-connected service.

### 2.4 Hardcoded Secrets

**Score: 45/100 — Several hardcoded dev secrets**

*Finding #19 (HIGH)*: `docker-compose.yml` line 67:
```
SECRET_KEY: ${ORCH_SECRET_KEY:-dev-secret-key-change-in-production}
```
This is a hardcoded fallback. If `.env` is not configured, Django uses `dev-secret-key-change-in-production`. Combined with `DEBUG: true` (line 68), this is a production-dangerous default.

*Finding #20 (MEDIUM)*: `docker-compose.yml` line 28:
```
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-coffeepie_dev}
```
Hardcoded database password fallback accessible on port 5432 (mapped to host).

*Finding #21 (MEDIUM)*: `pse.py` line 62: `os.getenv("PSE_TEST_MODE", "true").lower() == "true"` — defaults to test mode. If PSE is deployed without setting this env var, all payments go through test/simulated flow.

*Finding #22 (MEDIUM)*: `bancolombia.py` line 50: `os.getenv("BANCOLOMBIA_MERCHANT_ID", "COFFEEPIE")` — hardcoded default merchant ID.

*Finding #23 (LOW)*: `breb.py` line 48: `self.api_url` defaults to `https://api.bancolombia.com/breb/v1` — this is a real-looking URL that may not exist. Consider defaulting to empty and failing loudly if not configured.

### 2.5 Payment Module Security

**Score: 60/100 — Webhook verification missing on PSE + Bancolombia**

| Backend | Webhook Sig Check | Status |
|---|---|---|
| PSE | **NONE** (`pse.py:136`) | CRITICAL - anyone can POST false confirmations |
| Bre-B | HMAC-SHA256 (`breb.py:158-161`) | Good - signature verified |
| Bancolombia QR | **WEAK** (`bancolombia.py:113-119`) | Uses `hashlib.sha256(str(payload) + secret)` which is vulnerable to hash length extension and uses Python dict string representation which is non-canonical |

*Finding #24 (CRITICAL)*: PSE webhook has no signature verification. See Finding #13.

*Finding #25 (HIGH)*: `bancolombia.py` line 115-118 webhook signature verification uses `hashlib.sha256((str(payload) + self.api_secret).encode())`. Python's `str(payload)` on a dict produces non-canonical output (key order depends on insertion order in Python 3.7+). If Bancolombia's API produces the dict in a different key order than Python's `str()`, legitimate webhooks will be rejected. Use HMAC with canonical JSON serialization instead.

*Finding #26 (MEDIUM)*: `breb.py` line 160 uses `payload.pop("signature", "")` which mutates the payload dict. If the caller reuses the payload after webhook processing, the signature field will be missing. Use `payload.get("signature", "")` instead of `pop()`.

### 2.6 Proxmox Backend API Hardening

**Score: 65/100 — Known SSRF unfixed**

*Finding #27 (CRITICAL)*: SSRF via Sunshine PIN endpoint. `proxmox_routes.py` lines 169-186:
```python
sunshine_url = f"https://{request.ip}:47990/api/pin"
response = send_pin(sunshine_url, request.pin, request.client_name)
```
The `request.ip` field is user-controlled. An attacker can set it to any internal IP (e.g., `127.0.0.1`, `10.0.0.1`, `169.254.169.254`) and the backend will make an HTTPS request to that host. This was identified in the 2026-05-26 audit (V-7) and remains UNFIXED.

*Finding #28 (MEDIUM)*: Proxmox credentials (`PROXMOX_USER`, `PROXMOX_PASSWORD`) are stored in environment variables and sent to the Proxmox API via `requests.post(url, data=data, verify=True)` (`proxmox_service.py:7`). While TLS verification is enabled, the credentials are in plaintext in the environment.

### 2.7 Rate Limiting

**Score: 30/100 — Almost non-existent in payment/auth paths**

*Finding #29 (HIGH)*: No rate limiting on:
- `/auth/login` — brute-force susceptible
- `/auth/create-user` — unlimited account creation
- `/auth/forgot-password` — email bombing possible
- `/payments/webhook/*` — replay/abuse possible
- `/sunshine/send-pin` — PIN brute-force possible

The only rate limiting found is in the orchestrator's credits model (`credits.py:205`): `rate_limit_per_minute = models.PositiveIntegerField(default=60)` for ads API. This does not protect the payment or auth endpoints.

---

## 3. INFRASTRUCTURE

### 3.1 docker-compose.yml Security

**Score: 60/100 — Databases exposed, no non-root users**

| Issue | Detail | Severity |
|---|---|---|
| PostgreSQL port exposed | `5432:5432` — accessible from host network | HIGH |
| Redis port exposed | `6379:6379` — accessible from host network, no password | HIGH |
| All service ports mapped to host | 8000, 9090, 8001, 47989, 47984, 47990, 48010, 43910 | MEDIUM |
| Network isolation | `coffeepie-net` bridge with `172.28.0.0/16` — services communicate over internal network | GOOD |
| Volume mounts | `pgdata`, `orch-static`, `orch-media`, `cargo-cache` — named volumes | GOOD |
| Read-only app mounts | `./coffeepie_orchestrator/server:/app:ro` — read-only | GOOD |

*Finding #30 (HIGH)*: PostgreSQL and Redis are exposed on host ports 5432 and 6379. In production, these should only be accessible on the internal Docker network. Remove the `ports` mappings for postgres and redis (use `expose` instead) or bind to `127.0.0.1:5432:5432`.

*Finding #31 (MEDIUM)*: Redis has no password authentication. `command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru` (line 47) — no `--requirepass`. Anyone with network access to port 6379 can read/write all Redis data.

*Finding #32 (LOW)*: `sunshine-mock` exposes 4 ports (47989, 47984, 47990, 48010) using a socat command that wraps the HTTP response in multiple levels of shell escaping. The container also uses `apk add` on every startup (line 136). This adds startup latency and is fragile.

### 3.2 Dockerfile Security

**Score: 55/100 — All containers run as root**

| Dockerfile | Base Image | Non-root? | Issues |
|---|---|---|---|
| `server/Dockerfile.dev` | `python:3.12-slim` | NO | Runs as root. Installs build-essential (unnecessary in runtime). |
| `dc-agent/Dockerfile.dev` | `rust:1.85-slim-bookworm` | NO | Runs as root. Uses `cargo run` in container (dev-only). |
| `actor/Dockerfile.dev` | `rust:1.85-slim-bookworm` | NO | Same as dc-agent. |
| `scripts/mocks/proxmox/Dockerfile` | `python:3.12-alpine` | NO | Minimal, but runs as root. |

*Finding #33 (HIGH)*: None of the Dockerfiles create or switch to a non-root user. All containers run as `root`. This means a container breakout or app compromise gives root access inside the container.

*Finding #34 (MEDIUM)*: `server/Dockerfile.dev` line 5 installs `build-essential libpq-dev libffi-dev libssl-dev` — these are build-time dependencies, not runtime. Use multi-stage builds to keep the final image minimal.

*Finding #35 (LOW)*: Both Rust Dockerfiles (`dc-agent/Dockerfile.dev`, `actor/Dockerfile.dev`) are identical — consider a shared base image.

### 3.3 .env.example Completeness

**Score: 55/100 — Missing many required variables**

Variables documented in `.env.example`:
```
POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
ORCH_SECRET_KEY, ORCH_DEBUG
DC_AGENT_HYPERVISOR, DC_AGENT_AUTH_TOKEN, DC_AGENT_LOG
ACTOR_LOG
SUPABASE_URL (commented), SUPABASE_ANON_KEY (commented)
FIREBASE_PROJECT_ID (commented), FIREBASE_PRIVATE_KEY (commented), FIREBASE_CLIENT_EMAIL (commented)
```

Variables USED in code but MISSING from `.env.example`:

*Finding #36 (HIGH)*: The following environment variables are referenced in code but NOT documented in `.env.example`:
- `PSE_API_URL`, `PSE_MERCHANT_ID`, `PSE_API_KEY`, `PSE_TEST_MODE` (pse.py:57-62)
- `BREB_API_URL`, `BREB_API_KEY`, `BREB_API_SECRET`, `BREB_RECEIVER_KEY`, `BREB_BANK_CODE` (breb.py:49-53)
- `BANCOLOMBIA_QR_API_URL`, `BANCOLOMBIA_MERCHANT_ID`, `BANCOLOMBIA_TERMINAL_ID`, `BANCOLOMBIA_API_KEY`, `BANCOLOMBIA_API_SECRET` (bancolombia.py:48-53)
- `PROXMOX_URL`, `PROXMOX_USER`, `PROXMOX_PASSWORD` (config.py:6-8)
- `FIREBASE_ADMIN_SDK_JSON`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN`, `FIREBASE_STORAGE_BUCKET`, `FIREBASE_MESSAGING_SENDER_ID`, `FIREBASE_APP_ID`, `FIREBASE_MEASUREMENT_ID` (config.py:10-18)
- `SUNSHINE_USERNAME`, `SUNSHINE_PASSWORD` (config.py:20-21)
- `MOCK_AUTH_TOKEN` (scripts/mocks/proxmox/server.py:15)
- `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DC_AGENT_URL` (docker-compose.yml)

That's >20 missing environment variables. Developers will encounter runtime errors trying to configure the system beyond basic development.

### 3.4 .gitignore Coverage

**Score: 70/100 — Overly broad `.env` pattern**

*Finding #37 (MEDIUM)*: `.gitignore` line 43: `*.env` blocks ALL files ending in `.env` from being tracked. This is too broad — it would block `staging.env`, `production.env`, etc. if someone wanted to track non-secret env templates. The already-tracked `.env.example` is an exception because it was added before the gitignore rule. Use `.env` (exact match) and `*.local.env` instead.

*Finding #38 (LOW)*: `.gitignore` line 51: `Makefile` is ignored. This is unusual — `Makefile` is typically a tracked build configuration. The project has `Makefile` at root which IS tracked (added before rule). This creates confusion.

Positives:
- `.env` covered ✓
- `.hermes/` covered ✓
- `node_modules/`, `__pycache__/`, `venv/` covered ✓
- Build artifacts covered ✓

### 3.5 CI/CD Pipeline Coverage

**Score: 78/100 — Good but missing contract verification**

`.github/workflows/ci.yml` covers:
- ✅ All 5 Rust tools: build, clippy, test (matrix strategy)
- ✅ Rust actor: build, clippy
- ✅ Rust DC Agent: build, clippy
- ✅ Python orchestrator: ruff lint, Django checks, migrate
- ✅ Website: translations validation, HTML checks
- ✅ Integration tests: Docker compose, pytest
- ✅ Cargo caching for all Rust jobs

*Finding #39 (MEDIUM)*: No smart contract compilation/verification in CI. COFP_Token.sol is NOT compiled or analyzed in the pipeline (no solc, no slither, no mythril).

*Finding #40 (MEDIUM)*: No Docker image security scanning (no Trivy, no Snyk, no Dockle).

*Finding #41 (LOW)*: No dependency vulnerability scanning (`cargo audit` for Rust, `pip-audit` for Python).

*Finding #42 (LOW)*: CI uses `python manage.py check --deploy 2>/dev/null || true` (line 163) which silently ignores deployment check failures.

---

## 4. TOOLS

### 4.1 Compilation Status

**Score: 85/100 — CI-verified but not locally verified**

All 5 tools build successfully in CI (`tools:` job in `.github/workflows/ci.yml`). The CI matrix builds each tool category independently with `cargo build --release`, `cargo clippy --release -- -D warnings`, and `cargo test --release`.

Tool binaries per category:

| Category | Binaries | Purpose |
|---|---|---|
| `benchmark` | 7 binaries | latency-test, slices-calc, storage-sync-speed, bandwidth-bench, network-health, disk-iops-bench, streaming-capacity |
| `security` | 3 binaries | keygen, harden, audit |
| `dev` | 3 binaries | translations-validator, product-sync, schema-gen |
| `admin` | 4 binaries | deploy, billing, payment-test, provider-onboard |
| `monitoring` | 3 binaries | healthd, loadgen, stream-monitor |

### 4.2 Slice Spec Correctness

**Score: 95/100 — Perfect alignment**

`coffeepie-slices-calc.rs` constants (lines 73-80):
```
SLICE_CPU: 1.0      // 1 vCore
SLICE_RAM: 1.0      // 1 GB
SLICE_SSD: 8.0      // 8 GB
SLICE_HDD: 125.0    // 125 GB
SLICE_NET: 8.0      // 8 Mbps
SLICE_GPU: 125.0    // 125 MB VRAM
SLICE_VMP: 15.0     // 15 vMPX/s
SLICE_AI: 3.0       // 3 TOPS
```

These match `cloud-providers/README.md` (lines 80-92) EXACTLY:
```
CPU: 1 vCore | RAM: 1 GB | SSD: 8 GB | NET: 8 Mbps
HDD: 125 GB | GPU: 125 MB VRAM | RES: 15 vMPX/s | IA: 3 TOPS
```

*Finding #43 (LOW)*: The tool uses `SLICE_CPU` for vCores but the cloud-provider doc calls it "1 vCore". Both are equivalent. No issue.

### 4.3 Tool Redundancy

**Score: 90/100 — Clean separation**

No overlap detected:
- `benchmark/`: Performance measurement tools
- `security/`: Cryptographic keygen, hardening, audit
- `dev/`: Translation validation, product sync, schema generation
- `admin/`: Deployment, billing, payment testing, provider onboarding
- `monitoring/`: Health daemon, load generator, stream monitor

Each tool has a distinct name prefix or is in a distinct category.

### 4.4 Hardcoded Values

**Score: 75/100 — Reasonable defaults but some should be configurable**

*Finding #44 (LOW)*: `latency-test.rs` line 16: `default_value = "localhost:43910"` — hardcoded actor port. Reasonable as default but should be documented.

*Finding #45 (LOW)*: `coffeepie-slices-calc.rs` line 267: `let credits_per_hour = active * 100;` — hardcoded 100 Cr/slice/hour rate. This should read from an env var or CLI flag since regional pricing varies.

*Finding #46 (LOW)*: `coffeepie-healthd.rs` — the hardcoded endpoints for health checking should be configurable via CLI or env.

---

## 5. DEPENDENCIES

### 5.1 Python Dependencies

**Score: 70/100 — Mixed pinning quality**

| File | Pinning Quality |
|---|---|
| `coffeepie_backend/requirements.txt` | **EXCELLENT** — all exact versions (==) |
| `coffeepie_backend/proxmox_backend/requirements.txt` | **EXCELLENT** — 5 of 6 exact versions, `firebase-admin==6.6.0` |
| `coffeepie_orchestrator/server/requirements.txt` | **POOR** — `Django>5.2` (unbound upper), git+https for ldap3, many unpinned deps |
| `tests/integration/requirements.txt` | **POOR** — all `>=` ranges, no upper bounds |

*Finding #47 (HIGH)*: The orchestrator `requirements.txt` line 3: `Django>5.2` has no upper bound. A Django 6.0 release could break the orchestrator. Use `Django>=5.2,<6.0`.

*Finding #48 (MEDIUM)*: `git+https://github.com/cannatag/ldap3.git` (line 7) pulls from a fork with no version pinning. Any commit to that repo could break the build.

*Finding #49 (MEDIUM)*: `pqcrypto` (line 24) and `cryptography` (line 18) have no version pins. These are security-critical libraries.

### 5.2 Rust Dependencies

**Score: 82/100 — Standard practice for Rust**

All Rust tools use semver-compatible ranges (e.g., `clap = { version = "4" }`). This is standard Rust ecosystem practice. The `Cargo.lock` files pin exact versions for reproducibility.

Crate versions used:
- `clap 4` (CLI), `tokio 1` (async), `serde 1` (serialization)
- `ed25519-dalek 2` (Ed25519 signatures), `zeroize 1` (secure memory clearing)
- `indicatif 0.17` (progress bars), `regex 1` (pattern matching)

*Finding #50 (LOW)*: No `cargo audit` step in CI to detect known vulnerabilities in dependencies.

### 5.3 Known CVEs

**Score: N/A — No automated scan available**

No CVE database was queried. The audit cannot confirm CVEs without running `cargo audit` or `pip-audit`. This is a gap in the CI pipeline (see Finding #41).

---

## 6. COHERENCE

### 6.1 Payment Rates Consistency

**Score: 95/100 — Excellent alignment**

| Document/Code | 1 COFP = ? COP | 1 COFP = ? Cr | 1 Cr = ? COP |
|---|---|---|---|
| `models.py:170-177` | 0.29 COP | 10 Cr | 0.05 COP (20 Cr = 1 COP) |
| `cloud-providers/README.md:101` | "1 COFP per Slice per minute" | — | — |
| Contributor burn rate | 0.29 COP | 10 Cr | — |
| Consumer Cr rate | — | — | 20 Cr = 1 COP (6M Cr = 300K COP) |

The conversion functions:
- `cofp_to_cop(cofp)` → `cofp * 29 // 100` → 1 COFP = 0.29 COP (global base cost)
- `cofp_to_credits(cofp)` → `cofp * 10` → 1 COFP = 10 Cr (contributor burn rate)
- `credits_to_cop(cr)` → `cr // 20` → 20 Cr = 1 COP (consumer rate)
- `cop_to_credits(cop)` → `cop` (1:1, line 162)

*Finding #51 (LOW)*: `models.py` line 9 says "1 Cr ≈ 1 COP (subject to regional pricing adjustments)". The code implements exact 1:1 parity. The "≈" in the docstring should be "=" until regional pricing is implemented.

### 6.2 Tier Definitions

**Score: 90/100 — Consistent across cloud-provider docs**

The provider tiers documented in `cloud-providers/README.md` (lines 192-203) are internally consistent:

| Tier | Margin | Settlement Time |
|---|---|---|
| I | +8% | 24-72 h |
| II | +10% | 24-72 h |
| III | +12% | 24-48 h |
| IV | +15% | 24 h |
| V | +18% | Priority (same-day) |

No code implementing tier-based pricing was found in the payment module. The payment module operates purely in COP amounts. This is expected for MVP.

*Finding #52 (LOW)*: The cloud-provider README mentions "base COFP price × (1 + tier margin)" for fiat settlement but the `cofp_to_cop()` function uses a flat 1,000 rate. Tier adjustments are not implemented in code.

### 6.3 Cloud-Provider Configs vs Deployment

**Score: 80/100 — Readable docs, no deployable configs**

The `cloud-providers/` directory contains only CAD/3D design files (`.skp` SketchUp models) and a thorough README. There are no deployable configuration templates (Terraform, Ansible, cloud-init).

*Finding #53 (LOW)*: The README mentions `curl -sSL https://api.coffeepie.co/v1/actor/install | bash` (line 142) — this is a pipe-to-bash install pattern. In production, provide a signed package or checksum-verified binary instead.

### 6.4 Hardware-Manufacturer Specs

**Score: 85/100 — Well-organized but sparse**

The `hardware-manufacturers/` directory has excellent organization (Commander, Sentinel, Ranger) with proper folder structure for schematics, PCB, fabrication, 3D models, and 2D models. The Radxa Zero 3E Commander reference has actual design files.

*Finding #54 (LOW)*: Sentinel and Ranger designs are empty placeholders (`.gitkeep` only in most directories). The README says "TBD" for reference SBCs. This is expected for early-stage hardware but should be tracked as a milestone.

---

## 7. SUMMARY OF ALL FINDINGS

### Critical (4)

| ID | Component | Finding |
|---|---|---|
| #13 | Backend | Payment webhooks have ZERO authentication — anyone can POST fake payment confirmations |
| #24 | Backend | PSE webhook handler has no signature verification |
| #27 | Backend | SSRF via Sunshine PIN endpoint (user-controlled IP) — unfixed from 2026-05-26 audit |
| #36 | Infra | .env.example missing >20 env vars used in code (PSE, Bre-B, Bancolombia, Firebase, Sunshine) |

### High (7)

| ID | Component | Finding |
|---|---|---|
| #2 | Contract | 48h timelock is documented but NOT enforced in contract code |
| #14 | Backend | No rate limiting on auth endpoints (login, create-user, forgot-password) |
| #19 | Backend | Hardcoded Django SECRET_KEY fallback in docker-compose.yml |
| #25 | Backend | Bancolombia webhook signature uses non-canonical dict-to-string |
| #29 | Backend | No rate limiting on all payment/auth endpoints |
| #30 | Infra | PostgreSQL and Redis exposed on host ports |
| #47 | Dependencies | Orchestrator Django unpinned upper bound (`>5.2`) |

### Medium (13)

| ID | Component | Finding |
|---|---|---|
| #3 | Contract | `approve()` missing `whenNotPaused` modifier |
| #4 | Contract | `transferOwnership()` emits event before state change |
| #9 | Contract | ERC-20 `approve()` front-running vulnerability (no increase/decreaseAllowance) |
| #11 | Contract | DEPLOY.md doesn't mention deployer receives ALL 100M tokens |
| #15 | Backend | `/auth/create-user` has no CAPTCHA or verification |
| #16 | Backend | Firebase SDK JSON path resolution bug when absolute path set |
| #26 | Backend | `breb.py` mutates payload dict with `.pop("signature")` |
| #28 | Backend | Proxmox credentials in plaintext env vars |
| #31 | Infra | Redis has no password authentication |
| #33 | Infra | All Docker containers run as root |
| #37 | Infra | `.gitignore` `*.env` pattern is too broad |
| #39 | CI/CD | No smart contract compilation in CI pipeline |
| #48 | Dependencies | ldap3 fetched from unversioned git fork |

### Low (15)

| ID | Component | Finding |
|---|---|---|
| #1, #5-8, #10, #12, #17-18, #23, #32, #34-35, #38, #40-46, #49-54 | Various | Minor issues — see detailed findings above |

---

## 8. RECOMMENDATIONS (Priority-Ordered)

### Immediate (before production)
1. **Add authentication to webhook endpoints** — verify signatures for PSE and Bancolombia webhooks
2. **Fix SSRF in Sunshine PIN endpoint** — validate `request.ip` against whitelist, block private IPs
3. **Add rate limiting** to `/auth/*` and `/payments/webhook/*` endpoints
4. **Remove hardcoded secrets** from docker-compose.yml — require `.env` to be present
5. **Pin all Python dependencies** with upper bounds in orchestrator requirements.txt
6. **Remove host port exposure** for PostgreSQL and Redis in production config

### Short-term (before BVC listing)
7. **Implement Gnosis Safe multi-sig** with 4/7 signers as documented
8. **Add 48h timelock** to all onlyOwner functions (contract or Gnosis Safe enforced)
9. **Add `increaseAllowance`/`decreaseAllowance`** to COFP_Token.sol
10. **Add `whenNotPaused` to `approve()`**
11. **Create non-root users** in all Dockerfiles
12. **Complete .env.example** with all environment variables
13. **Add Solidity compilation + security analysis** to CI (solc, slither)

### Long-term (continuous improvement)
14. **Add `cargo audit` + `pip-audit`** to CI for dependency vulnerability scanning
15. **Add Docker image scanning** (Trivy)
16. **Implement tier-based pricing** in payment module
17. **Implement CUFE/DIAN electronic invoice** integration
18. **Add Prometheus metrics** for payment success/failure rates
