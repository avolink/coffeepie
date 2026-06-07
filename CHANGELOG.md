# Changelog

All notable changes to the Coffee Pie® project.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

## [0.1.0] — 2026-06-07

### Token Economics
- **Elastic supply model** — COFP has no supply cap. Initial supply of 100M, emitted at 1 COFP per Slice·min by Providers. `remint()` replaced with `mint()`.
- Wallet holding limit standardized to 100'000'000'000 COFP (or 10% of total supply) across all docs.
- COFP unit defined: 1 COFP = 1 Coffee Pie® Slice served for 1 minute.
- **Three-tier conversion architecture**: 1 COFP = 0.29 COP (global base), 20 Cr = 1 COP (consumer rate), 10 Cr per COFP (contributor burn rate).
- Contributors can burn COFP for Credits — closes the gap where Contributors earned tokens they couldn't use.
- Provider Fiat Settlement Tiers I-V defined with margin structure (+8% to +18%).
- Two-currency model codified: COFP (supply-side) + Credits/Cr (demand-side). Consumers never touch COFP.
- Conversion functions in `payments/models.py` updated: `cofp_to_cop`, `cofp_to_credits`, `credits_to_cop`.

### Documentation
- **AGENTS.md** — comprehensive project rules, conventions, architecture, and agent guidance.
- **CONSTITUTION.md** — project sovereignty, autonomous governance, revenue distribution.
- **API.md** — full REST + WebSocket API reference.
- **PKI.md** — public key infrastructure and certificate lifecycle.
- **DISASTER_RECOVERY.md** — runbooks for catastrophic failure scenarios.
- **EMERGENCY_PROTOCOL.md** — attack surface analysis, vulnerability registry, incident response.
- **TRANSLATIONS.md** — i18n infrastructure and translation workflow.
- **BOUNTIES.md** — contributor bounty program.
- **CONTRIBUTING.md** — onboarding guide for new contributors.
- **ROADMAP.json** — structured project roadmap.

### Audits
- **COHERENCE.md** — cross-document policy consistency audit (9 categories, 88/100 score).
- **COHESION.md** — structural file inventory audit.
- **BACKEND_INFRA_AUDIT.md** — smart contract + backend security audit.
- **ORCHESTRATOR_AUDIT.md** — orchestrator security review.
- **SECURITY_AUDITS.md** — DC Agent security audit (13 findings, all resolved).
- **SEO_AUDITS.md** — search engine optimization audit.
- **UI-UX_AUDITS.md** — user interface and experience audit.
- **WEBSITE_AUDIT.md** — website security and performance audit.

### Blockchain
- `COFP_Token.sol` — TRC-20 smart contract (Solidity 0.8.20) for TRON network.
- `DEPLOY.md` — Remix IDE + TronLink deployment guide with post-deployment checklist.
- Gnosis Safe 4/7 multi-sig governance spec with 48-hour timelock.

### CLI Tools (20 tools across 5 categories)
- **admin/** — billing, deploy, payment-test, provider-onboard
- **benchmark/** — bandwidth, disk IOPS, latency, network health, slices calculator, storage sync, streaming capacity
- **dev/** — product sync, schema generation, translations validator
- **monitoring/** — health daemon, load generator, stream monitor
- **security/** — audit scanner, system hardener, key generator

### Website
- Multi-language support: Spanish (primary), English (primary), Portuguese, French, German, Japanese, Russian, Hindi, Arabic, Korean, Chinese, Greek.
- Vanilla JS/HTML/CSS — no frameworks, no TypeScript, no CSS preprocessors.
- Product gallery, cart, store, panel, pricing, cloud providers, manufacturers, investor portal pages.
- Firebase hosting with 301 redirects for renamed pages.
- Cart uses `data-cp-no-translate` to maintain Spanish layout for all languages.
- Translation pipeline: `translations.json` → instant language switching without reload.

### Frontend (Qt/QML)
- Coffee Pie® Qt GUI in kiosk mode with login, machine selection, payment gateways.
- Moonlight embedded for Sunshine streaming client.
- CMake build system with Python prototyping layer (PySide6).

### Backend
- **Orchestrator** — Django (OpenUDS fork), transport plugins, Sunshine integration.
- **Actor** — Rust workspace, client-side agent, WebSocket worker pattern.
- **DC Agent** — Rust axum server, hypervisor abstraction, heartbeat + capacity reporting.
- **proxmox_backend** — FastAPI service, Proxmox API abstraction with Firebase auth.
- **Payments** — PSE, Bre-B, Bancolombia QR integration.
- **Sunshine** — streaming server submodule (server-side encoding: NVENC, VAAPI, AMF).

### Infrastructure
- Docker Compose 7-service local dev stack (postgres, redis, orchestrator, dc-agent, proxmox-mock, sunshine-mock, actor).
- CI pipeline (`.github/workflows/ci.yml`) — build, lint, test, compose smoke.
- Integration test suite (pytest + docker compose fixtures, 649 lines).
- `Makefile` — setup, test, lint, logs, status targets.

### Documentation Tooling
- `scripts/check-doc-consistency.py` — automated policy coherence checker (9 checks across all core docs). CI-ready.
- `.gitignore` — Rust `target/`, Qt `.rcc/`, Python `.venv/`, and CMake artifacts covered.

---

## [0.0.0] — 2026-05-19

### Added
- Initial commit. Project bootstrap.
- Multi-language website with `translations.json`.
- Hero section, language menu, automated locale detection.
- README.md with project overview.
