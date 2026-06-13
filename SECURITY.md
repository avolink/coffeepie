# Security Policy

Coffee Pie® runs untrusted workloads on community-operated nodes and moves real value (COFP, Credits, provider payouts). Security is a first-class concern. Thank you for helping keep the ecosystem and its users safe.

## Supported Versions

The project is in **Alpha (TRL7), v0.1.0-alpha**. Only the `main` branch and the latest tagged release receive security fixes during this phase.

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ |
| `v0.1.0-alpha` | ✅ |
| Older / forks | ❌ |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue, pull request, or Discord message for security vulnerabilities.**

Report privately via one of:

1. **GitHub Private Vulnerability Reporting** — the "Report a vulnerability" button under this repository's **Security** tab (preferred).
2. **Email** — `security@coffeepie.co`. Encrypt sensitive details if possible; request our PGP key at the same address.

Please include:

- A description of the vulnerability and its impact (what can an attacker do?).
- Affected component (orchestrator, actor, dc-agent, tunnel-server, backend, frontend, website, smart contract, hardware).
- Step-by-step reproduction, proof-of-concept, or affected `file:line` references.
- Any suggested remediation.

### What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement of your report | within **72 hours** |
| Initial severity assessment | within **7 days** |
| Fix or mitigation plan | within **30 days** for High/Critical |
| Public disclosure | coordinated, after a fix ships (typically ≤ 90 days) |

We follow **coordinated disclosure**. We will credit you in the release notes and `audits/SECURITY_AUDITS.md` unless you prefer to remain anonymous. A paid bug-bounty program (rewarded in COFP) is under construction and will launch once the COFP token is deployed to TRON mainnet. See `BOUNTIES.md` for the planned reward tiers. In the interim, high-impact reports may be rewarded in COFP at the maintainers' discretion once the token is live.

## Scope

**In scope:** code in this repository — the orchestrator (Django/UDS fork), Rust actor/dc-agent/tunnel-server, FastAPI backend, Qt frontend, website, the `COFP_Token` smart contract, CLI tools, and hardware reference designs.

**Out of scope / report upstream instead:**

- Vulnerabilities in vendored third parties (`coffeepie_backend/sunshine`, `coffeepie_frontend/moonlight-embedded`) — report to LizardByte / Moonlight upstream, then notify us so we can pin a patched version.
- Findings already documented in [`audits/SECURITY_AUDITS.md`](audits/SECURITY_AUDITS.md) (known technical debt). New exploitation paths for those are still welcome.
- Denial of service via volumetric/network flooding, social engineering, or physical attacks on a specific operator's datacenter.

## Operator & Node Safety

If you run a node on the QFDM Network, harden it before exposing it:

- Never reuse the sample credentials, `SECRET_KEY`, or `RSA_KEY` shipped in `*.sample` / `.env.example` files. Generate fresh values (`tools/security` → `coffeepie-keygen`, `coffeepie-harden`).
- Run with `DEBUG=False`, an explicit `ALLOWED_HOSTS` whitelist, TLS certificate verification enabled, and secure cookie flags in production.
- Keep secrets in environment variables or a vault — never commit them. The repository's `.gitignore` blocks `.env` / `*.env`; do not override it.
- Review [`EMERGENCY_PROTOCOL.md`](EMERGENCY_PROTOCOL.md) and [`DISASTER_RECOVERY.md`](DISASTER_RECOVERY.md) for incident response.
- IPv8 (IETF draft-thain-ipv8-02) is on the roadmap (2035 or RFC maturity) — its OAuth8 JWT and ACL8 would provide future network-layer defense-in-depth on the L2/L3/L4 stretched VLAN, complementing application-layer security.

## A Note on History

A Firebase service-account key and API key were committed early in development. Both were **rotated** and the credentials purged from the published history. If you find any credential that still authenticates against live infrastructure, treat it as a vulnerability and report it privately as above.
