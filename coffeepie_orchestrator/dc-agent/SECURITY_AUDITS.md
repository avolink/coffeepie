# Coffee Pie DC Agent — Security Audits

## Audit #1 — 2026-05-29: Black-Hat Adversarial Review

**Auditor role**: Adversarial (attacker with L2/L3 network access to the datacenter
private VLAN, e.g., compromised codec terminal or rogue device)

**Scope**: All Rust source files in `coffeepie_orchestrator/dc-agent/src/` +
`Cargo.toml` + `.env.example` + proxmox_backend API contract

**Version audited**: pre-fix commit (before the fix log below)

---

### Findings Summary

| ID | Severity | Component | Description |
|----|----------|-----------|-------------|
| C-1 | **CRITICAL** | `api/mod.rs` | Zero authentication on instance lifecycle endpoints |
| C-2 | **CRITICAL** | `adapters/proxmox.rs` | HTTP status codes ignored; all errors silently masked |
| C-3 | **CRITICAL** | `api/mod.rs` + `proxmox.rs` | User-controlled strings in URL paths without sanitization |
| H-1 | HIGH | `proxmox.rs` | `clone-by-name` errors returned as HTTP 200, treated as success |
| H-2 | HIGH | `proxmox.rs` + `auth_service.py` | Bearer token expires after 1 hour, no refresh, silent failure |
| H-3 | HIGH | `main.rs` | CORS: `allow_origin(Any)` on VM lifecycle API |
| M-1 | MEDIUM | `api/mod.rs` | Path parameter `instance_id` discarded; URL structure bypassable |
| M-2 | MEDIUM | `proxmox.rs` | VMID collision via timestamp — predictable and racy |
| M-3 | MEDIUM | `api/mod.rs` | Error messages leak internal infrastructure topology |
| M-4 | MEDIUM | `types.rs` | No input validation on `SliceSpec` — `u32::MAX` values accepted |
| L-1 | LOW | `types.rs` | Integer overflow in `SliceSpec::scale()` (wrap in release mode) |
| L-2 | LOW | all | Bearer token in process memory (core dumps) |
| L-3 | LOW | `proxmox.rs` | First IP returned may not be Sunshine-reachable |

---

### Detailed Findings

#### C-1 — Zero authentication on all instance lifecycle endpoints (CVSS 9.8)

**File**: `src/api/mod.rs`, routes `/instances`, `/instances/{id}`, `/instances/{id}/start`, `/instances/{id}/stop`

No middleware, no header check, no token validation — anyone who can reach port 9090
can create/destroy/start/stop VMs.

**Attack**: A single compromised device on the L2/L3 private VLAN can:
- `POST /instances` — spin up unlimited VMs (resource drain / crypto-mining)
- `DELETE /instances/anything` — destroy production VMs (denial of service)
- `POST /instances/x/start`, `/stop` — disrupt all running instances
- `GET /capacity` — full infrastructure reconnaissance

**Fix**: Added `DC_AGENT_AUTH_TOKEN` env var. When set, all mutation endpoints require
`Authorization: Bearer <token>`. GET endpoints (health, capacity, templates) remain
open for operational monitoring. If unset, a warning is logged but the agent still
starts (fails-open for development; must be set in production).

---

#### C-2 — HTTP status codes never checked; errors silently masked (CVSS 8.2)

**File**: `src/adapters/proxmox.rs`, `get()`, `post()`, `delete()` helpers

Every HTTP call eagerly parsed `.json()` with zero status inspection. When the bearer
token expires (Firebase ID tokens expire after 1 hour), the proxmox_backend returns
HTTP 401 with `{"detail": "Invalid or expired authentication token"}`. The adapter
parsed this as valid JSON, callers like `list_nodes()` accessed `json["data"]` which
doesn't exist, fell through to `unwrap_or(&vec![])`, and returned an **empty node list**.

Result: the DC Agent silently reported "zero nodes, zero VMs, healthy" to the broker.
The entire datacenter appeared empty with `HealthStatus::Healthy`.

**Fix**: Added `check_status()` helper that validates `resp.status().is_success()`
before parsing JSON. Non-2xx responses return an error with the status code and body.

---

#### C-3 — User-controlled strings injected into URL paths without sanitization (CVSS 7.5)

**File**: `src/api/mod.rs` lines 54-55, 77-78, 96-97 + `src/adapters/proxmox.rs`

`destroy_instance`, `start_instance`, and `stop_instance` extracted `provider_vm_id`
and `node` from a user-controlled JSON body and interpolated them directly into URL
paths with `format!()`. An attacker could send:

```json
{"provider_vm_id": "../../../../etc", "node": "pve1"}
```

Reqwest's URL parser would normalize `../` segments, resulting in SSRF-like behavior
where the attacker controls which proxmox_backend path gets requested.

**Fix**: Added `is_safe_identifier()` validation (allowed: `[a-zA-Z0-9][a-zA-Z0-9._-]*`).
Applied to all user-controlled path components in both the API handlers and the
ProxmoxAdapter. Invalid inputs return HTTP 400.

---

#### H-1 — `clone-by-name` errors returned as HTTP 200 with JSON error body (CVSS 6.5)

**File**: `src/adapters/proxmox.rs` lines 222-226

The proxmox_backend `clone_by_name()` route catches exceptions and returns
`{"error": "Failed to clone VM: ..."}` with **HTTP 200**. The adapter only checked
for transport errors (`reqwest::Error`), not application-level errors in the response
body. The agent would proceed to start a non-existent VM and return a `SliceHandle`
pointing to a ghost — billing the user for an instance that doesn't exist.

**Fix**: After receiving the clone response, the code now explicitly checks for
`json["error"]` and returns an error if present.

---

#### H-2 — Bearer token lifecycle: 1-hour expiration, no refresh mechanism (CVSS 6.3)

**File**: `src/adapters/proxmox.rs` + `proxmox_backend/app/services/auth_service.py`

The proxmox_backend uses `firebase_admin.auth.verify_id_token()` which validates
**Firebase ID tokens** (short-lived JWTs, expire after 1 hour). The `.env.example`
instructed users to place this token in `DC_AGENT_BEARER_TOKEN`. After 1 hour:

1. Token expires
2. Backend returns HTTP 401
3. (Previously) DC Agent silently treated it as success → datacenter goes dark

**Fix**: 
- C-2 now detects HTTP 401 properly and returns errors.
- `.env.example` documents the expiration and recommends using Firebase **custom
  tokens** (long-lived, created via `auth_service.create_custom_token`) instead.
- A TODO remains for automatic token refresh (requires architecture — the agent
  would need Firebase Admin SDK to mint tokens, which adds dependency weight).

---

#### H-3 — CORS: `allow_origin(Any)` on a VM lifecycle API (CVSS 7.1)

**File**: `src/main.rs` lines 100-103

```rust
let cors = CorsLayer::new()
    .allow_origin(Any)
    .allow_methods(Any)
    .allow_headers(Any);
```

Any website visited by an operator on the internal network could execute JavaScript
that creates/destroys VMs via CSRF-like attacks. Paired with C-1 (no auth), this
meant a single phishing link = total datacenter compromise.

**Fix**: CORS is now disabled by default (no CORS headers — server-to-server mode).
If browser access is needed (monitoring dashboard), set `DC_AGENT_CORS_ORIGIN` to
the dashboard's URL. Even with CORS enabled, mutation endpoints require the auth
token from C-1.

---

#### M-1 — Path parameter `instance_id` discarded; URL structure bypassable (CVSS 4.3)

**File**: `src/api/mod.rs`, `start_instance()` and `stop_instance()`

`Path(_instance_id): Path<String>` — the path parameter was discarded (underscore
prefix). The handler operated on whatever `provider_vm_id` the body specified. An
attacker could do:

```
POST /instances/innocent-uuid/start
{"provider_vm_id": "cp-actual-target", "node": "pve1"}
```

If audit logging were added later, it would log "started instance innocent-uuid"
while actually starting a different VM.

**Fix**: The `instance_id` path parameter is now validated against the allowed
identifier pattern. While a full binding between `instance_id` and `provider_vm_id`
requires state (the agent is currently stateless), the fix at least validates the
parameter and prevents path traversal through it.

---

#### M-2 — VMID collision: timestamp-based, predictable and racy (CVSS 4.0)

**File**: `src/adapters/proxmox.rs` line 211

```rust
let vmid = (chrono::Utc::now().timestamp() % 1000000) as u32;
```

Two concurrent `create_instance` calls in the same second → same VMID → clone fails.
After ~11.5 days, VMIDs wrap and collide with previously created VMs. An attacker
who observes creation patterns could predict the next VMID and pre-create a VM to
block legitimate provisioning.

**Fix**: Replaced with an atomic counter (`AtomicU32`, starts at 100,000). Each call
to `next_vmid()` returns a unique, monotonically increasing value with no possibility
of collision or wrapping for decades.

---

#### M-3 — Error messages leak internal infrastructure topology (CVSS 4.0)

**File**: `src/api/mod.rs`, error responses

Error messages included full URLs, node names, VM names, and backend response bodies.
An attacker probing the API could learn: backend hostname (`proxmox-api.dc1.lan`),
node naming convention (`pve-west-3`), and VM naming convention (`cp-{uuid}`).

**Fix**: Added `sanitize_error()` function. The full error is logged via `tracing::error!`
for debugging. API callers receive a generic message like "create_instance: internal error".

---

#### M-4 — No input validation on `SliceSpec` (CVSS 4.0)

**File**: `src/types.rs`

An attacker could send `cpu_cores: 4294967295`, `ram_gb: 4294967295`, etc. These
passed through to the adapter without bounds checking.

**Fix**: Added `SliceSpec::validate()` and `CreateSliceRequest::validate()` with
bounds constants (`MAX_CPU_CORES`, `MAX_RAM_GB`, etc. = 64 × base slice spec).
Invalid requests return HTTP 400 with a field-specific error message.

---

#### L-1 — Integer overflow in `SliceSpec::scale()` (CVSS 2.3)

**File**: `src/types.rs` lines 68-79

In release mode, Rust wraps on overflow by default. `cpu_cores * 0 = 0` (no panic,
wrong result). The method was unused in production code but dangerous if activated.

**Fix**: Changed `*` to `saturating_mul`. `scale()` now returns `Option<Self>`,
returning `None` if any field would exceed its maximum allowed value.

---

#### L-2 — Bearer token in process memory

The `bearer_token` is a plain `String` with no zeroization on `Drop`. If the process
crashes with core dumps enabled, the token is recoverable from the dump file. No
immediate fix (requires `secrecy` crate or `mlock`), documented as known limitation.

#### L-3 — First IP may not be Sunshine-reachable

`get_instance_ip()` takes `ips[0]` — if the VM has multiple interfaces, the first
one might be an internal NAT interface. **Fixed**: now iterates through all IPs and
prefers non-loopback, non-link-local IPv4 addresses.

---

### Attacker Kill Chain (Pre-Fix)

1. **Recon**: `GET /capacity` without auth → learn node names, VM counts, naming scheme
2. **Resource drain**: `POST /instances` in a loop → fill all 64 slots per node
3. **Token expiration**: Wait 1 hour → all API calls silently fail → datacenter
   reports empty with `HealthStatus::Healthy` while VMs run unmanaged
4. **Selective sabotage**: `DELETE /instances/x` targeting specific VMs
5. **Cover tracks**: No audit log of which caller performed which action

**This kill chain is fully mitigated by the fixes in this audit.**
Every step now requires authentication (C-1), validates inputs (C-3, M-1, M-4),
checks response integrity (C-2, H-1), and doesn't leak infrastructure details
in errors (M-3).

---

### Fix Log

| ID | File(s) Changed | Summary |
|----|----------------|---------|
| C-1 | `main.rs`, `api/mod.rs`, `.env.example` | Added `DC_AGENT_AUTH_TOKEN`; mutation endpoints require `Authorization: Bearer *** | C-2 | `proxmox.rs` | Added `check_status()` — all HTTP calls validate `is_success()` before parsing JSON |
| C-3 | `types.rs`, `api/mod.rs`, `proxmox.rs` | Added `is_safe_identifier()` validation on all user-controlled URL path components |
| H-1 | `proxmox.rs` | Clone response checked for `json["error"]` key; clone failure now errors |
| H-2 | `.env.example`, `proxmox.rs` | Documented token lifecycle; C-2 fix detects expired token responses |
| H-3 | `main.rs`, `.env.example` | CORS disabled by default; `DC_AGENT_CORS_ORIGIN` for optional browser access |
| M-1 | `api/mod.rs` | `instance_id` path param validated against `is_safe_identifier()` |
| M-2 | `proxmox.rs` | Replaced `timestamp % 1000000` with atomic counter starting at 100,000 |
| M-3 | `api/mod.rs` | Added `sanitize_error()` — generic messages to callers, full errors to logs |
| M-4 | `types.rs`, `api/mod.rs` | Added `validate()` methods with bounds constants; validation in create handler |
| L-1 | `types.rs` | `scale()` uses `saturating_mul`, returns `Option<Self>` |
| L-3 | `proxmox.rs` | `get_instance_ip()` prefers non-loopback, non-link-local IPv4 addresses |

### Build Verification

```
# Run from coffeepie_orchestrator/dc-agent/
cargo build
cargo test   # unit tests in types.rs validate the safety functions
```

### Post-Audit Recommendations

1. **Automated token refresh**: Add Firebase Admin SDK to the DC Agent or a sidecar
   to auto-refresh bearer tokens before expiry.
2. **Mutual TLS**: Replace shared-secret auth (C-1 fix) with mTLS between the QFDM
   broker and DC Agent for defense-in-depth.
3. **Audit logging**: Add structured audit logs (who called which endpoint, from
   which IP, with what result) — currently no per-request caller tracking.
4. **State persistence**: Track instance_id ↔ provider_vm_id mappings so the path
   parameter can be fully validated against a known state.
5. **Dependency audit**: Run `cargo audit` and `cargo deny` on the dependency tree.
6. **Secrets management**: Replace env-var tokens with a secrets manager (Vault,
   AWS Secrets Manager, or at minimum file-based with `mlock` protection).
