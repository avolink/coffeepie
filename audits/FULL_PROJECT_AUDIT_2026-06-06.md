# Coffee Pie — Full Project Audit 2026-06-06

**Generated:** 2026-06-06
**Auditor:** Hermes Agent (3 parallel subagents + coordinator)
**Coverage:** Full monorepo — Rust, Python, Website, Blockchain, Docker/CI, Cross-component
**Toolchain:** Python 3.14.4, flake8, mypy, bandit, node --check, cargo (static analysis)

---

## Executive Summary

| Component | Security | Code Quality | Structure | Overall | Trend |
|-----------|----------|-------------|-----------|---------|-------|
| Rust (actor, tunnel-server, dc-agent, tools) | 55/100 | 72/100 | 78/100 | **68/100** | — |
| Python (orchestrator, proxmox, payments) | 58/100 | 65/100 | 82/100 | **68/100** | — |
| Website (vanilla HTML/CSS/JS) | 48/100 | 68/100 | 62/100 | **59/100** | NEW |
| Blockchain (COFP_Token.sol) | 72/100 | 90/100 | 85/100 | **82/100** | — |
| Infrastructure (Docker, CI, Makefile) | 65/100 | 78/100 | 70/100 | **71/100** | — |
| Cross-component Coherence | — | — | 95/100 | **95/100** | — |
| **PROJECT AVERAGE** | **60/100** | **75/100** | **79/100** | **74/100** | +1 |

### Strengths
- **Doc policy coherence passes all 10 automated checks** — wallet limits, COFP unit, conversion rates perfectly consistent
- **Zero Python syntax errors** — all .py files compile cleanly
- **Zero JavaScript syntax errors** — all source .js files pass node --check
- **Zero CSS syntax errors** — all braces balanced across 8 CSS files
- **Zero hardcoded secrets** in source code — everything via environment variables
- **DC Agent has proper auth** after prior security audit — mutation endpoints require bearer token
- **No SQL injection vulnerabilities** — Django ORM + parameterized queries used properly
- **Solidity ^0.8.20** — built-in overflow protection, modern compiler

### Critical Weaknesses (12 findings)

| # | Finding | Component | Severity |
|---|---------|-----------|----------|
| 1 | **Tunnel server panics on network I/O failure** — `.expect()` on every read/write | Rust | CRITICAL |
| 2 | **Unsafe Send/Sync on Rc<UnsafeCell>** — aliasing UB in tunnel server | Rust | CRITICAL |
| 3 | **`panic!()` in `MakeWriter`** — log disk full = server crash | Rust | CRITICAL |
| 4 | **`coffeepie_backend/app/` has NO authentication** — all VM/CT CRUD endpoints open | Python | CRITICAL |
| 5 | **48h timelock documented but NOT in smart contract** — single owner key = infinite mint | Blockchain | CRITICAL |
| 6 | **Smart contract: pause doesn't block mint/burn** — tokens can flow while "paused" | Blockchain | HIGH |
| 7 | **Nginx coffeepie.conf has stale Spanish URLs** — all redirects broken | Website | CRITICAL |
| 8 | **Nginx missing all security headers** — no CSP, HSTS, X-Frame-Options | Website | CRITICAL |
| 9 | **vanilla-gallery.js: zero HTML escaping on product data** — innerHTML XSS risk | Website | HIGH |
| 10 | **No Rust fmt check in CI** — formatting drift undetected | Infra | MEDIUM |
| 11 | **No tunnel-server in CI at all** — the most security-critical component untested | Infra | HIGH |
| 12 | **Environment variable sprawl** — .env.example missing >20 vars used by components | Cross | MEDIUM |

---

## 1. Cross-Component Policy Coherence

**Score: 95/100** — PASS

All 10 automated policy checks pass. Wallet holding limit (100B COFP, 10% of supply), initial supply (100M), elastic supply model, COFP unit definition (1 COFP = 1 Slice·min), contributor/provider burn rules, backend enforcement, and conversion rates are consistent across CONSTITUTION.md, README.md, AGENTS.md, blockchain/DEPLOY.md, and code files.

**No coherence issues found.**

---

## 2. Rust Components

**Score: 68/100**

Covers: `coffeepie_orchestrator/actor` (50+ .rs), `coffeepie_orchestrator/tunnel-server` (46 .rs), `coffeepie_orchestrator/dc-agent` (7 .rs), `tools/admin` (4 binaries), `tools/benchmark` (7 binaries), `tools/dev` (3 binaries), `tools/monitoring` (3 binaries), `tools/security` (3 binaries)

### 2.1 Critical Issues

#### C1: Tunnel server panics on network I/O failure
**File:** `coffeepie_orchestrator/tunnel-server/crates/shared/src/crypt/stream.rs:97,103`
**Issue:** `.expect("Failed to write data")` and `.expect("Failed to read data")` are called for EVERY packet. A single network error panics the entire tunnel server.
**Fix:** Convert to `Result<()>` and propagate errors. This is in the hot data path — every packet goes through these calls.

#### C2: Unsafe Send/Sync on Rc<UnsafeCell> — aliasing UB
**File:** `coffeepie_orchestrator/tunnel-server/crates/server/src/session/mod.rs:71-81`
**Issue:** `unsafe impl Send/Sync for SessionRecoveryBuffer` wraps `Rc<UnsafeCell<...>>`. `Rc` is `!Send + !Sync` by design to prevent data races. This manually overrides that invariant. Additionally, `unsafe { &mut *self.0.get() }` creates a `&mut` from a `&self` reference — callers can create multiple `&mut` aliases simultaneously.
**Fix:** Replace `Rc<UnsafeCell<Vec<u8>>>` with `Arc<Mutex<Vec<u8>>>` for thread-safe access, or use `UnsafeCell` only if you can prove (and document) single-threaded access at the call sites.

#### C3: `panic!()` in MakeWriter — double panic crash
**File:** `coffeepie_orchestrator/tunnel-server/crates/shared/src/log.rs:101`
**Issue:** Inside a `MakeWriter` implementation, there's a `panic!()` call on log rotation failure. A `panic!()` inside `MakeWriter` during an existing panic produces a double-panic (abort). If the log disk fills up during a panic, the server hard-crashes with no panic message.
**Fix:** Silently fall back to stderr or a null writer instead of panicking.

### 2.2 High Severity

#### H1: `.unwrap()` on address parse
**File:** `tunnel-server/crates/server/src/config/mod.rs:35`
**Issue:** `addr_str.parse().unwrap()` panics on invalid config.
**Fix:** Return `Result<SocketAddr>` and propagate.

#### H2: Typo in struct name
**File:** `tunnel-server/crates/shared/src/errors.rs:4`
**Issue:** `ErrorWithAddres` — missing trailing 's'. Should be `ErrorWithAddress`.

#### H3: DC Agent `.expect()` at startup
**File:** `dc-agent/src/main.rs:39,98,160`
**Issue:** `.expect()` on env var parsing, adapter build, CORS origin. Panics on misconfiguration.
**Fix:** Use `anyhow::Result` with `?` propagation so the error is logged cleanly.

#### H4: DC Agent falls back to "0.0.0.0" on IP lookup failure
**File:** `dc-agent/src/adapters/proxmox.rs:315`
**Issue:** `get_instance_ip()` returns "0.0.0.0" on error, which is an unreachable address.
**Fix:** Return `Result<String>` or `Option<String>` so callers handle the error.

#### H5: 11x `.unwrap()` on Mutex::lock()
**File:** `tunnel-server/crates/shared/src/system/trigger.rs`
**Issue:** All 11 calls panic on poisoned mutex.
**Fix:** Use `.lock().expect("trigger lock poisoned")` or handle gracefully.

### 2.3 Medium Severity

#### M1: ~75 lines of duplicate input validation
**File:** `dc-agent/src/api/mod.rs`
**Issue:** `destroy_instance`, `start_instance`, `stop_instance` share ~25 identical lines.
**Fix:** Extract to a validation helper function.

#### M2: 30+ `.unwrap()` on `serde_json::to_string_pretty()`
**Files:** Various tools
**Issue:** JSON serialization `.unwrap()` — panics if struct contains NaN or non-serializable data.
**Fix:** Use `.expect("serialization failed")` with a context message.

#### M3: `.partial_cmp().unwrap()` on NaN floats
**Files:** `network-health.rs:244`, `latency-test.rs:107`, `coffeepie-loadgen.rs`
**Issue:** Float NaN values produce `None` from `partial_cmp()`, which `.unwrap()` panics on.
**Fix:** Filter NaN values before sorting, or use `unwrap_or(Ordering::Equal)`.

### 2.4 Low Severity

- `#![allow(dead_code, unused_variables)]` in `connection/mod.rs` suppresses all warnings — remove
- Edition inconsistency: tools use 2021, tunnel-server uses 2024 — standardize
- `rand = "0.8"` in benchmark tools is outdated (dc-agent uses 0.10)
- FLTK auto-generated files have mixed tabs/spaces and 144+ `.unwrap()` calls — auto-generated, low priority

### 2.5 Unsafe Block Inventory

| File | Lines | Risk | Description |
|------|-------|------|-------------|
| `tunnel-server/session/mod.rs:71-72` | `unsafe impl Send/Sync` | **CRITICAL** | `Rc` is not thread-safe |
| `tunnel-server/session/mod.rs:81` | `unsafe { &mut *self.0.get() }` | **CRITICAL** | `mut_from_ref` aliasing |
| `tunnel-server/log.rs:253` | `unsafe { set_var }` | Low | Test-only, `#[cfg(test)]` |

---

## 3. Python Components

**Score: 68/100**

Covers: `coffeepie_backend/proxmox_backend` (FastAPI, 28 files), `coffeepie_backend/payments` (10 files), `coffeepie_backend/app` (5 files), `coffeepie_orchestrator/server` (Django, ~300 files), `scripts/` (3 files)

### 3.1 Critical Issues

#### C4: `coffeepie_backend/app/` — ALL ENDPOINTS UNAUTHENTICATED
**File:** `coffeepie_backend/app/controllers/proxmox_controller.py`
**Endpoints:** `/clone-vm`, `/clone-ct`, `/create-vm`, `/create-ct`, `/vms`, `/cts`, `/update-vm`, `/delete-vm`, `/control-vm/*`, `/control-ct/*`, `/vm/*/config`, `/vm/*/network`
**Issue:** Zero authentication on any endpoint. No bearer token, no API key, no CSRF, no session check. Anyone with network access to this service can clone, create, modify, or delete VMs and containers.
**Fix:** Add Firebase Bearer token authentication matching the pattern in `proxmox_backend/app/dependencies.py:verify_bearer_token()`.

### 3.2 High Severity

#### H1: Bandit HIGH — xmlrpc without defusedxml (2x)
**Files:** `services/OpenNebula/on/client.py:35`, `services/Xen/xen/client.py:33`
**Issue:** XMLRPC parsing without `defusedxml`, vulnerable to XML entity expansion and other XML attacks.
**Fix:** Replace `xmlrpc.client` with `defusedxml.xmlrpc`.

#### H2: Bandit HIGH — SSL verify=False (1x)
**File:** `services/OpenShift/openshift/client.py:95`
**Issue:** `verify=False` on an OAuth token request. Man-in-the-middle can steal credentials.
**Fix:** Remove `verify=False` or add `# nosec` with justification (e.g., internal-only network, documented in AGENTS.md).

#### H3: Bandit HIGH — shell=True in transport scripts (4x)
**Files:** `transports/RDP/scripts/macosx/direct.py:30`, `transports/RDP/scripts/macosx/tunnel.py:37`, `transports/RDPEmbedded/scripts/macosx/direct.py:30`, `transports/RDPEmbedded/scripts/macosx/tunnel.py:37`
**Issue:** `subprocess` calls with `shell=True`.
**Fix:** Use list arguments and remove `shell=True`.

### 3.3 Medium Severity

#### M1: 8 active `pickle.loads()` uses — accepted risk
**Files:** `storage.py`, `auto_attributes.py`, `serializer.py`, `ticket_store.py`, `delayed_task_runner.py`, `user_interface.py`, `model.py`, `export.py`
**Issue:** All have `# nosec` annotations claiming controlled environments. Risk remains: if DB is compromised, pickle deserialization = RCE.
**Status:** Accepted technical debt. Documented in AGENTS.md §Known Technical Debt.

#### M2: 13 `requests` calls without timeout
**Files:** `proxmox_backend/app/services/proxmox_service.py` (12x), `sunshine_service.py` (1x)
**Issue:** No `timeout=` parameter. If Proxmox API is unresponsive, requests hang forever, tying up worker threads.
**Fix:** Add `timeout=30` to all `requests.get/post/put/delete` calls.

#### M3: 31 mypy type errors
**Files:** `payments/backends/*.py` (implicit Optional), `proxmox_routes.py` (attr-defined)
**Issue:** `param: str = None` should be `param: Optional[str] = None`.
**Fix:** Add `from typing import Optional` and fix type annotations.

### 3.4 Low Severity — Flake8 (135 issues)

- 65x E302: Missing 2 blank lines before functions
- 18x F401: Unused imports (worst in `proxmox_routes.py`)
- 13x E501: Lines >120 chars
- 10x W293: Blank line with whitespace
- 8x W292: Missing trailing newline
- Minor: E128, F811, F841, E131, E203, etc.

### 3.5 CSRF Exemptions — 5 found, all expected

All 5 CSRF exemptions are on SSO callbacks, REST API dispatchers, and MFA views — expected pattern for an API server. No new concerns.

---

## 4. Website

**Score: 59/100**

Covers: `coffeepie_website/public/` — HTML, CSS, JS, JSON, .htaccess, coffeepie.conf

### 4.1 Critical Issues

#### C7: Nginx coffeepie.conf — stale Spanish URLs
**File:** `coffeepie_website/coffeepie.conf:14-29`
**Issue:** All URL rewrites use old Spanish paths (`/precios`, `/tienda`, `/tutoriales`, `/acerca-de`, `/politica-de-envios`, `/politica-de-privacidad`, `/politica-de-retornos`, `/terminos-y-condiciones`, `/accesibilidad`, `/dispositivos-certificados`, `/fabricantes`, `/proveedores-nube`, `/portal-de-inversionistas`). Pages were renamed to English. The `try_files $uri.html` directives will fail on all these paths.
**Fix:** Update all `location` blocks to English URLs: `/pricing`, `/store`, `/tutorials`, `/about`, `/shipping-policy`, `/privacy-policy`, `/return-policy`, `/terms-and-conditions`, `/accessibility`, `/certified-devices`, `/manufacturers`, `/cloud-providers`, `/investor-portal`.

#### C8: Nginx missing all security headers
**File:** `coffeepie_website/coffeepie.conf`
**Issue:** No CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy. Only `listen 80` (no HTTPS). `server_tokens` left at default `on` (leaks nginx version).
**Fix:** Add security headers matching `.htaccess`:
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload";
add_header X-Content-Type-Options "nosniff";
add_header X-Frame-Options "SAMEORIGIN";
add_header Referrer-Policy "strict-origin-when-cross-origin";
add_header Content-Security-Policy "...";
server_tokens off;
```

### 4.2 High Severity

#### H1: vanilla-gallery.js — zero HTML escaping
**File:** `coffeepie_website/public/js/vanilla-gallery.js:171-183`
**Issue:** Product names, prices, images, and URLs are injected into HTML via string concatenation with no escaping:
```javascript
'<h3 class="vg-name">' + p.name + '</h3>'
'<img src="' + imgSrc + '" ...>'
'<span class="vg-price">' + p.price + '</span>'
```
Currently mitigated because data comes from a static trusted `products.json`. If a future feature loads products from an API or user-submitted source, this becomes exploitable XSS.
**Fix:** Use `textContent` for text fields, create elements via `document.createElement()` rather than innerHTML strings.

#### H2: cart.js escapeHtml doesn't escape quotes
**File:** `coffeepie_website/public/js/cart.js:48-52,285`
**Issue:** `escapeHtml()` converts `<`, `>`, `&` but NOT `"` or `'`. Image src is injected via template literal: `<img src="${escapeHtml(item.image)}" ...>`. A `"` in the image URL (via localStorage poisoning) breaks out of the `src` attribute.
**Fix:** Add `"` and `'` to `escapeHtml()` or use `encodeURIComponent()` for attribute values.

#### H3: cart.js productUrl from localStorage without validation
**File:** `coffeepie_website/public/js/cart.js:200-214`
**Issue:** `productUrl` from `item.url` (stored in localStorage) is injected into `<a href="${productUrl}">` without validation. A `javascript:` URL in localStorage would execute on click.
**Fix:** Validate product URLs against a whitelist of allowed domains/paths before rendering.

### 4.3 Medium Severity

#### M1: Duplicate cart.js with different functionality
**Files:** `coffeepie_website/public/js/cart.js` (10,665 bytes, canonical) vs `coffeepie_website/public/assets/cart.js` (6,850 bytes, stale)
**Issue:** Two different versions. `js/cart.js` is the active/current version. `assets/cart.js` is an older version missing translation support, variant handling, and quantity buttons. Its checkout button triggers `alert('Checkout en mantenimiento')`.
**Fix:** Delete `assets/cart.js`. Redirect all references to `js/cart.js`.

#### M2: Inconsistent localStorage language keys
**Files:** `js/lang.js` uses `cp_lang`, `404.html` uses `coffee_pie_lang`
**Issue:** Language preference set by the language switcher is invisible to the 404 page.
**Fix:** Standardize on `cp_lang` across all files.

#### M3: CSP with `unsafe-inline`
**File:** `coffeepie_website/public/.htaccess:80`
**Issue:** CSP has `script-src 'unsafe-inline'` and `style-src 'unsafe-inline'` — defeats CSP's XSS protection.
**Fix:** Use nonces or hashes for inline scripts/styles, or move them to external files.

#### M4: Duplicate files — firebase-init.js, product-accordion.js
**Files:** `assets/` and `js/` directories
- `js/firebase-init.js` and `assets/firebase-init.js` — identical
- `js/product-accordion.js` and `assets/product-accordion.js` — identical (LF vs CRLF only)
**Fix:** Delete the `assets/` copies. Redirect all references to `js/`.

### 4.4 Low Severity

- `html lang="es"` hardcoded on all pages despite lang.js detecting locale — should dynamically update
- Hardcoded domain in product `og:image` URLs (`https://coffeepie.co/assets/...`) — breaks in staging
- No CSP violation reporting (`report-uri` or `report-to`)
- `.htaccess` CSP allows `static.parastorage.com` and `static.avostatic.com` — overly broad, legacy from Wix
- `index-wix.css` at 5,548 brace pairs — legacy Wix CSS, should be audited for unused rules

### 4.5 Verified OK

| Check | Result |
|-------|--------|
| All 4 JSON files valid | ✓ `translations.json`, `products.json`, `assets/products.json`, `manifest.json` |
| All JS files pass `node --check` | ✓ (firebase-init.js uses ES modules — expected) |
| All 8 CSS files have balanced braces | ✓ |
| All HTML files have `<!DOCTYPE html>` + `<meta charset="UTF-8">` | ✓ |

---

## 5. Blockchain & Smart Contract

**Score: 82/100**

**File:** `blockchain/COFP_Token.sol` (126 lines, Solidity ^0.8.20)

### 5.1 Critical Issues

#### C5: 48h timelock documented but NOT in smart contract
**Issue:** `blockchain/DEPLOY.md:175` requires "48-hour timelock on all `onlyOwner` functions" but the contract has zero timelock. `mint()`, `pause()`, `unpause()`, `transferOwnership()` execute instantly.
**Fix:** Implement a timelock pattern:
```solidity
mapping(bytes32 => uint256) public timelock;
uint256 public constant TIMELOCK_DURATION = 48 hours;

function scheduleMint(address _to, uint256 _value) public onlyOwner {
    bytes32 txHash = keccak256(abi.encodePacked("mint", _to, _value, block.timestamp));
    timelock[txHash] = block.timestamp + TIMELOCK_DURATION;
}
function executeMint(address _to, uint256 _value, uint256 _timestamp) public onlyOwner {
    bytes32 txHash = keccak256(abi.encodePacked("mint", _to, _value, _timestamp));
    require(block.timestamp >= timelock[txHash], "COFP: timelock not expired");
    _mint(_to, _value);
    delete timelock[txHash];
}
```
Alternatively, deploy via Gnosis Safe with its built-in timelock module.

### 5.2 High Severity

#### H1: `pause()` doesn't block `mint()` or `burn()`
**Issue:** The `whenNotPaused` modifier is only on `transfer()` and `transferFrom()`. `mint()`, `burn()`, `burnFrom()`, `approve()` have no pause check. Tokens can still be minted and burned while the contract is "paused".
**Fix:** Add `whenNotPaused` to `mint()`, `burn()`, `burnFrom()`. Optionally add it to `approve()`.

#### H2: `transferOwnership()` — no two-step pattern
**Issue:** A typo in the new owner address permanently orphans the contract. No `acceptOwnership()` confirmation step.
**Fix:** Change to pending pattern:
```solidity
address public pendingOwner;
function transferOwnership(address _newOwner) public onlyOwner {
    pendingOwner = _newOwner;
}
function acceptOwnership() public {
    require(msg.sender == pendingOwner, "COFP: not pending owner");
    emit OwnershipTransferred(owner, pendingOwner);
    owner = pendingOwner;
    pendingOwner = address(0);
}
```

### 5.3 Medium Severity

#### M1: No event for constructor ownership
**Issue:** Constructor sets `owner = msg.sender` but doesn't emit `OwnershipTransferred(address(0), msg.sender)`. Inconsistent with other state changes.
**Fix:** Add `emit OwnershipTransferred(address(0), msg.sender);` in constructor.

#### M2: `approve()` not gated by pause
**Issue:** Allowance changes during a pause may be intentional or may not — unclear. If the emergency circuit breaker is meant to freeze all token activity, approve should also be paused.
**Assessment:** Minor — allowances don't move tokens. Decide intentionally.

### 5.4 Verified OK

| Check | Result |
|-------|--------|
| Solidity ^0.8.20 with built-in overflow protection | ✓ |
| No reentrancy risks (no external calls in state-changing functions) | ✓ |
| Events on all state changes (Transfer, Approval, Burn, Mint, OwnershipTransferred, Paused, Unpaused) | ✓ |
| Zero-address checks on transfer, mint, ownership | ✓ |
| Clear, readable code with section comments | ✓ |
| DEPLOY.md is thorough and well-documented | ✓ |
| Multi-sig governance path documented (Gnosis Safe 4/7) | ✓ |

---

## 6. Infrastructure

**Score: 71/100**

Covers: `docker-compose.yml`, `.github/workflows/ci.yml`, `Makefile`, `.env.example`

### 6.1 High Severity

#### H1: No tunnel-server in CI
**Issue:** CI has jobs for tools, actor, dc-agent, orchestrator, website, docs, integration — but NOT tunnel-server. The most security-critical component (handles all encrypted tunnel traffic) has zero CI coverage.
**Fix:** Add a `tunnel-server` CI job:
```yaml
tunnel-server:
  name: Rust tunnel-server
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: dtolnay/rust-toolchain@stable
    - run: cd coffeepie_orchestrator/tunnel-server && cargo build --release
    - run: cd coffeepie_orchestrator/tunnel-server && cargo clippy --release -- -D warnings
```

### 6.2 Medium Severity

#### M1: No Rust fmt check in CI
**Issue:** CI runs `cargo clippy` and `cargo build` but NOT `cargo fmt --check`. Formatting drift goes undetected.
**Fix:** Add `cargo fmt --check` to each Rust job.

#### M2: CI integration tests use `sleep 10`
**Issue:** `ci.yml:243` uses `sleep 10` for service readiness. Fragile — fast CI runners may need more time, slow ones waste time.
**Fix:** Replace with health-check polling:
```bash
for i in $(seq 1 30); do
  curl -s http://localhost:8001/health && break
  sleep 2
done
```

#### M3: `make clean` removes .env without backup
**File:** `Makefile:23`
**Issue:** `rm -rf .env` with no confirmation or backup. Destructive.
**Fix:** Add a confirmation prompt or backup: `cp .env .env.bak && rm .env`.

#### M4: Environment variable documentation gap
**File:** `.env.example`
**Issue:** Missing >20 env vars used by components: PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD, FIREBASE_API_KEY, SUNSHINE passwords, payment API keys (PSE_MERCHANT_ID, BREB_API_KEY, BANCOLOMBIA_API_KEY), TRON network settings, etc.
**Fix:** Add ALL environment variables from component `.env.example` files to the root `.env.example` with comments.

#### M5: Docker compose uses `cargo run` in containers
**Issue:** `docker-compose.yml:111` and `:168` use `cargo run --release` which compiles AND runs. Compilation in a container per-start degrades startup time significantly.
**Fix:** Use multi-stage Docker builds — compile in build stage, copy binary to runtime stage.

### 6.3 Low Severity

- `docker-compose.yml:64`: `DATABASE_URL` has `***` redaction
- `Makefile:116`: `sleep 10` for setup readiness — should poll
- `Makefile:45`: `sleep 5` for db-reset — should poll
- No `.dockerignore` files in Rust service directories
- `docker-compose.yml` uses `version: "3.9"` — deprecated in newer Docker, but compatible

---

## 7. Cross-Component Issues

### P1: Fire-and-forget Sunshine auth gap
The DC Agent (Rust) and proxmox_backend (FastAPI) both have proper auth. But the Django orchestrator's Sunshine launch view has zero authentication. Same operation (connecting to a VM Sunshine instance) protected in Rust, exposed in Django. **Cross-component auth inconsistency.**

### P2: Cart trust boundary is undefined  
The website stores cart data in localStorage (prices, quantities, totals). The backend payment module receives purchase data. Neither defines whether the backend recalculates prices from product database or trusts client-submitted totals. This MUST be clarified — backend should ALWAYS recalculate.

### P3: Port inconsistency in coffeepie.conf
`coffeepie.conf` references old Spanish URLs that were renamed to English. Nginx config is out of sync with `firebase.json`'s redirect rules.

### P4: Environment variable sprawl (see §6.2 M4)
Each subcomponent has its own `.env.example` with no master list.

### P5: Duplicate code across components
- Two different versions of `cart.js`
- Two copies of `firebase-init.js` and `product-accordion.js`
- Two different language preference keys (`cp_lang` vs `coffee_pie_lang`)

---

## 8. Prioritized Remediation Matrix

| # | Finding | Impact | Effort | Component | Status |
|---|---------|--------|--------|-----------|--------|
| 1 | coffeepie_backend/app/ NO auth | CRITICAL | MED | Python | NEW |
| 2 | Tunnel server panics on I/O | CRITICAL | HIGH | Rust | NEW |
| 3 | Unsafe Send/Sync on Rc | CRITICAL | HIGH | Rust | NEW |
| 4 | panic!() in MakeWriter | CRITICAL | LOW | Rust | NEW |
| 5 | 48h timelock not in contract | CRITICAL | MED | Blockchain | NEW |
| 6 | Nginx stale Spanish URLs | CRITICAL | LOW | Website | NEW |
| 7 | Nginx missing security headers | CRITICAL | LOW | Website | NEW |
| 8 | Smart contract pause gap | HIGH | LOW | Blockchain | NEW |
| 9 | vanilla-gallery.js no HTML escape | HIGH | MED | Website | NEW |
| 10 | cart.js escapeHtml no quotes | HIGH | LOW | Website | NEW |
| 11 | cart.js productUrl validation | HIGH | LOW | Website | NEW |
| 12 | No tunnel-server in CI | HIGH | MED | Infra | NEW |
| 13 | `requests` no timeout (13x) | MEDIUM | LOW | Python | NEW |
| 14 | mypy implicit Optional (17x) | MEDIUM | LOW | Python | NEW |
| 15 | Duplicate JS files (cart, firebase, accordion) | MEDIUM | LOW | Website | NEW |
| 16 | Flake8 cleanup (135 issues) | LOW | MED | Python | NEW |
| 17 | Environment variable docs | MEDIUM | MED | Cross | Known |
| 18 | No Rust fmt in CI | MEDIUM | LOW | Infra | NEW |
| 19 | CSP unsafe-inline | LOW | HIGH | Website | Known |
| 20 | Edition inconsistency (2021 vs 2024) | LOW | LOW | Rust | NEW |
| 21 | `make clean` destructive | LOW | LOW | Infra | NEW |
| 22 | `cargo run` in Docker (slow) | LOW | MED | Infra | NEW |

---

## 9. Appendix

### A. Verification Commands

To re-run any audit component:

```bash
# Doc coherence
python3 scripts/check-doc-consistency.py

# Python syntax check
find coffeepie_backend scripts coffeepie_orchestrator/server -name '*.py' \
  ! -path '*/__pycache__/*' ! -name '*.pyc' -exec python3 -m py_compile {} \;

# Python lint
cd coffeepie_backend && flake8 proxmox_backend/ payments/ app/

# Python security
cd coffeepie_orchestrator/server && bandit -r src/ -f txt

# Website JS syntax
find coffeepie_website/public -name '*.js' ! -path '*/_files/*' \
  -exec node --check {} \;

# Website JSON validity
for f in coffeepie_website/public/translations.json \
         coffeepie_website/public/data/products.json; do
  python3 -c "import json; json.load(open('$f')); print('✓ $f')"
done

# Rust check (needs toolchain)
cd coffeepie_orchestrator/dc-agent && cargo check

# Docker compose validate
docker compose config --quiet

# Integration tests
make test-integration
```

### B. Toolchain Status

| Tool | Available | Used |
|------|-----------|------|
| Python 3.14.4 | ✓ | py_compile, flake8, mypy, bandit |
| Rust toolchain | ✗ (not installed) | Static analysis only |
| Node.js | ✓ | --check for JS files |
| Docker | ✓ | compose config validation |
| Solidity compiler | ✗ (not installed) | Manual review only |

### C. Revision History

| Date | Changes |
|------|---------|
| 2026-06-06 | Initial full audit. 3 parallel subagents + coordinator. 22 findings. |

---

*This report supersedes all prior component audits (WEBSITE_AUDIT.md, ORCHESTRATOR_AUDIT.md, BACKEND_INFRA_AUDIT.md, COHESION.md, COHERENCE.md, SECURITY_AUDITS.md) as the single source of truth for audit status as of 2026-06-06.*
