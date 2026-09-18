# Contributing to Coffee Pie®

Welcome. Coffee Pie® is an open ecosystem — hardware, software, documentation, translations, testing, and community support are all valued contributions.

## Quick Start (5 minutes)

```bash
git clone https://github.com/avolink/coffeepie.git
cd coffeepie
cp .env.example .env
make setup
```

This starts PostgreSQL, Redis, orchestrator, DC Agent, actor, and mock services via Docker. No real hypervisor needed for development.

```bash
make status   # see all endpoints
make logs     # follow logs
make test     # run all tests
```

## What to Work On

| Skill set | Good first issues |
|-----------|-------------------|
| **Rust** | `tools/` — benchmark tools, harden new checks, deploy phases |
| **Python/Django** | Orchestrator transports, API endpoints, billing logic |
| **Qt/QML** | Frontend kiosk UI, Moonlight integration, settings screens |
| **Vanilla JS/HTML/CSS** | Website pages, translations, cart system, gallery |
| **Documentation** | Translating docs, improving READMEs, API reference |
| **Testing** | Integration tests, load testing, security fuzzing |
| **Hardware** | Codec Terminal firmware, SBC validation, PCB design |
| **Drivers** | Kernel drivers for ARM SBC hardware decoders (DRM/KMS, VAAPI, NPU, USB-IP, etc) — Codec Terminals run Debian Minimal |
| **Kernel** | Long-term contribution to Rust-for-Linux: write new Coffee Pie® kernel modules in Rust (e.g., QFDM slice-aware scheduler), port critical paths gradually over time to reduce memory bugs and zero-day exploits — no rewrite, decades-long collaborative effort |

Check `ROADMAP.json` for prioritized milestones and tasks. Issues labeled `good first issue` are beginner-friendly.

## Project Structure

```
coffeepie/
├── coffeepie_orchestrator/   # Django orchestrator + Rust actor + DC agent
│   ├── server/               # Django (OpenUDS fork)
│   ├── actor/                # Rust daemon (VM lifecycle, WS client)
│   ├── dc-agent/             # Rust hypervisor abstraction layer
│   └── tunnel-server/        # WebSocket tunnel for media signaling
├── coffeepie_frontend/       # Qt/QML desktop client + Moonlight
├── coffeepie_backend/        # FastAPI Proxmox backend
├── coffeepie_website/        # Vanilla HTML/CSS/JS public site
├── blockchain/               # COFP Token (TRC-20 on TRON)
├── hardware-manufacturers/   # Codec Terminal reference designs
├── cloud-providers/          # Datacenter provider docs
├── tools/                    # CLI tools (benchmark, security, dev, admin, monitoring)
│   ├── benchmark/            # latency, bandwidth, storage, streaming tests
│   ├── security/             # keygen, harden, audit
│   ├── dev/                  # translations-validator, product-sync, schema-gen
│   ├── admin/                # deploy, billing, payment-test, provider-onboard
│   └── monitoring/           # healthd, loadgen, stream-monitor
├── tests/                    # Integration & unit test suites
│   └── integration/          # Docker-based full-stack tests
├── scripts/                  # Utility scripts, init SQL, mock servers
│   └── mocks/proxmox/        # Proxmox API mock for development
├── coffeepie_backend/payments/  # PSE, Bre-B, Bancolombia QR payment module
├── docker-compose.yml        # Local development environment
├── Makefile                  # Common commands
└── ROADMAP.json              # Milestones and task tracking
```

## Development Workflow

### 1. Pick an issue
Find something in `ROADMAP.json` or ask in Discord.

### 2. Branch
```bash
git checkout -b feat/my-feature
# or: fix/bug-description, docs/readme-update, chore/ci-improvement
```

### 3. Develop
- **Rust**: `cargo build`, `cargo test`, `cargo clippy` before committing
- **Python**: `ruff check .`, `python manage.py test`
- **Website**: Test in browser at `file://` or via `python -m http.server` in `coffeepie_website/public/`
- **Translations**: Edit `coffeepie_website/public/translations.json` only. Run `translations-validator` from `tools/dev/` (`cargo run --bin translations-validator`).

### 4. Pre-commit checks
```bash
make lint    # Rust clippy + Python ruff
make test    # all test suites
```

### 5. Commit
```bash
git add .
git commit -m "feat: add network health diagnostic tool"
```

Prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`, `security:`

### 6. Pull Request
Push and open a PR against `main`. CI runs automatically (build + lint + test).

## Code Conventions

### Rust
- `cargo fmt` (standard rustfmt)
- `cargo clippy -- -D warnings` must pass
- Follow actor worker pattern: subscribe to broadcast channel, filter by type
- Use `shared::log` macros for logging
- Platform-specific code: `#[cfg(target_family = "...")]`

### Python (Django)
- Follow OpenUDS module patterns
- Transports: `server/src/uds/transports/<Name>/`
- All user-facing strings: `gettext_noop / _()`
- Settings via environment variables, never hardcoded

### Website
- **NO frameworks** (no React, Vue, Angular, Tailwind, Bootstrap)
- **NO TypeScript** — vanilla JS (latest ECMAScript)
- **NO CSS preprocessors** — vanilla CSS
- Spanish-first content (project founded in Colombia)
- Translations via `translations.json` only

### General
- Numeric format: apostrophe `'` as thousands separator (`1'000'000`)
- Dates: `YYYY-MM-DD` international format
- No emojis in code or commit messages unless asked
- Never commit secrets, tokens, or credentials

## Translation Guidelines

1. Edit only `coffeepie_website/public/translations.json`
2. The key is the **Spanish** text. `es` field = same as key.
3. Add all 12 languages: `es, en, pt, fr, de, ru, hi, ja, zh, ko, ar, el` (CI fails if any are missing)
4. **Never translate** these (they stay identical in all languages):
   - Emails (`accesibility@coffeepie.co`)
   - Physical addresses
   - Brands with ® or ™ (`Coffee Pie®`, `Commanders™`)
   - Project names (`QFDM`, `OpenUDS`, `Sunshine`, `Moonlight`)
   - URLs and API endpoints
   - Technical specs (`1 Wh`, `8 GB`, `3 TOPS`)
   - Social media handles
5. Run `tools/dev` → `translations-validator` before committing
6. See `TRANSLATIONS.md` for full policy

## Security

- Report vulnerabilities privately: `security@coffeepie.co`
- See `audits/SECURITY_AUDITS.md` for known technical debt
- All PRs are scanned by CI for common issues
- Keys must never be committed — use `.env` or environment variables
- The `EMERGENCY_PROTOCOL.md` covers incident response

## Getting Help

- **Discord**: [Coffee Pie® Community](https://discord.gg/coffeepie)
- **Documentation**: `AGENTS.md`, `CONSTITUTION.md`, `README.md`
- **Roadmap**: `ROADMAP.json`

## License

Coffee Pie® uses a **tiered license model** — there is no single blanket license. See [`LICENSE`](LICENSE) and [`CONSTITUTION.md`](CONSTITUTION.md) for the binding terms. In summary:

- **QFDM Core & Orchestrator** — Open Core (source-available, proprietary); commercial use by codec-terminal manufacturers, large-scale/enterprise deployments, and competitors is subject to **QFDM Royalty Fees** — patent royalties for use of the patented QFDM system (Patent NC2025/0012723), not a software license fee.
- **Frontend & Drivers** — Apache-2.0.
- **Hardware Design** — CERN Open Hardware License.

By contributing you agree to the project **Contributor License Agreement (CLA)**, which keeps the ecosystem commercially viable under its BIC (Benefit and Collective Interest) status. Contributions are licensed under the tier that applies to the component you modify.
