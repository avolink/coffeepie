# Coffee Pie — Master Audit Index

**Latest Audit:** 2026-06-06 — [FULL_PROJECT_AUDIT_2026-06-06.md](FULL_PROJECT_AUDIT_2026-06-06.md) (**CURRENT** — 22 findings across all components)  
**Previous Audit:** 2026-06-05  
**Coverage:** Full monorepo — Rust, Python, Website, Blockchain, Docker/CI, Cross-component

---

## Audit Files

| # | File | Component | Type | Score | Date |
|---|------|-----------|------|-------|------|
| ★ | [FULL_PROJECT_AUDIT_2026-06-06.md](FULL_PROJECT_AUDIT_2026-06-06.md) | **ALL** | **Comprehensive** | **74/100** | **2026-06-06** |
| 1 | [WEBSITE_AUDIT.md](WEBSITE_AUDIT.md) | coffeepie_website | Security, Code Quality, Structure, Performance | **50/100** | 2026-06-05 |
| 2 | [ORCHESTRATOR_AUDIT.md](ORCHESTRATOR_AUDIT.md) | coffeepie_orchestrator | Security, Code Quality, Structure, Dependencies | **66/100** | 2026-06-05 |
| 3 | [BACKEND_INFRA_AUDIT.md](BACKEND_INFRA_AUDIT.md) | Backend, Blockchain, Infra, Tools | Security, Code Quality, Structure, Dependencies | **75/100** | 2026-06-05 |
| 4 | [COHESION.md](COHESION.md) | Cross-component | Cross-references, Terminology, Numeric consistency | **80/100** | 2026-05-30 |
| 5 | [COHERENCE.md](COHERENCE.md) | Cross-component | Policy, Economic model, Voting rights | **95/100** | 2026-06-04 |
| 6 | [SECURITY_AUDITS.md](SECURITY_AUDITS.md) | Full repo | Vulnerability history, findings, remediation | — | 2026-05-26 |
| 7 | [UI-UX_AUDITS.md](UI-UX_AUDITS.md) | coffeepie_website | Accessibility, UX, Design | **4.5/10** | 2026-05-26 |
| 8 | [SEO_AUDITS.md](SEO_AUDITS.md) | coffeepie_website | Search Engine Optimization | **42/100** | 2026-05-26 |

---

## Executive Summary (updated 2026-06-06)

| Component | Security | Code Quality | Structure | Overall | Trend |
|-----------|----------|-------------|-----------|---------|-------|
| Rust (actor, tunnel-server, dc-agent, tools) | 55/100 | 72/100 | 78/100 | **68/100** | NEW |
| Python (orchestrator, proxmox, payments) | 58/100 | 65/100 | 82/100 | **68/100** | NEW |
| Website (vanilla HTML/CSS/JS) | 48/100 | 68/100 | 62/100 | **59/100** | NEW |
| Blockchain (COFP_Token.sol) | 72/100 | 90/100 | 85/100 | **82/100** | — |
| Infrastructure (Docker, CI, Makefile) | 65/100 | 78/100 | 70/100 | **71/100** | NEW |
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

### Critical Weaknesses (12 findings from 2026-06-06 audit)

1. **coffeepie_backend/app/ has NO authentication** — all VM/CT CRUD endpoints completely open (Python §C4)
2. **Tunnel server panics on network I/O failure** — `.expect()` on every packet read/write (Rust §C1)
3. **Unsafe Send/Sync on Rc<UnsafeCell>** — aliasing UB in tunnel server session buffer (Rust §C2)
4. **`panic!()` in MakeWriter** — log disk full crashes server via double-panic (Rust §C3)
5. **48h timelock documented but NOT in smart contract** — single owner key = infinite mint (Blockchain §C5)
6. **Smart contract: pause doesn't block mint/burn** — tokens can flow while contract is "paused" (Blockchain §H1)
7. **Nginx coffeepie.conf has stale Spanish URLs** — all URL rewrites broken (Website §C7)
8. **Nginx missing all security headers** — no CSP, HSTS, X-Frame-Options (Website §C8)
9. **vanilla-gallery.js: zero HTML escaping on product data** — innerHTML XSS risk (Website §H1)
10. **No tunnel-server in CI at all** — most security-critical component untested (Infra §H1)
11. **13 `requests` calls without timeout** — worker threads hang on unresponsive Proxmox API (Python §M2)
12. **Duplicate cart.js with different functionality** — two versions, assets/ stale and broken (Website §M1)

---

## Cross-Component Alignment (New Findings 2026-06-06)

### P1: Fire-and-forget Sunshine auth gap
The DC Agent (Rust) and proxmox_backend (FastAPI) both have proper auth. But the Django orchestrator's Sunshine launch view has zero authentication. Same operation (connecting to a VM Sunshine instance) protected in Rust, exposed in Django.

### P2: Cart trust boundary is undefined  
The website stores cart data in localStorage (prices, quantities, totals). The backend payment module receives purchase data. Neither defines whether the backend recalculates prices from product database or trusts client-submitted totals. Backend MUST recalculate — never trust client prices.

### P3: Port inconsistency in coffeepie.conf
`coffeepie.conf` references old Spanish URLs (pago-seguro, tienda, carrito) that were renamed to English. Nginx config is out of sync with firebase.json's redirect rules. See also Website §C7.

### P4: Environment variable sprawl
`.env.example` at root is missing >20 env vars used by components. Each subcomponent (DC Agent, proxmox_backend, orchestrator, payments) has its own `.env.example` with no master list.

### P5: Duplicate code across components
- `cart.js` exists in both `public/js/cart.js` and `public/assets/cart.js` — different versions
- `firebase-init.js` duplicated in `public/js/` and `public/assets/`
- `product-accordion.js` duplicated
- Two different language preference keys (`cp_lang` vs `coffee_pie_lang`)

---

## Remediation Priority Matrix (updated 2026-06-06)

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
| 13 | requests no timeout (13x) | MEDIUM | LOW | Python | NEW |
| 14 | mypy implicit Optional (17x) | MEDIUM | LOW | Python | NEW |
| 15 | Duplicate JS files | MEDIUM | LOW | Website | NEW |
| 16 | Flake8 cleanup (135 issues) | LOW | MED | Python | NEW |
| 17 | Environment variable docs | MEDIUM | MED | Cross | Known |
| 18 | No Rust fmt in CI | MEDIUM | LOW | Infra | NEW |
| 19 | CSP unsafe-inline | LOW | HIGH | Website | Known |
| 20 | Edition inconsistency (2021 vs 2024) | LOW | LOW | Rust | NEW |
| 21 | make clean destructive | LOW | LOW | Infra | NEW |
| 22 | cargo run in Docker (slow) | LOW | MED | Infra | NEW |

---

## How to Use This Report

1. **Start with the Master Index** (this file) — understand the big picture
2. **Drill into component audits** — WEBSITE_AUDIT.md, ORCHESTRATOR_AUDIT.md, BACKEND_INFRA_AUDIT.md
3. **Check cross-component alignment** — COHESION.md and COHERENCE.md for policy/rules consistency
4. **Review security history** — SECURITY_AUDITS.md for what was fixed and what remains
5. **Fix in priority order** — Critical → High → Medium → Low, tackling low-effort items first for quick wins

---

*Re-run after major structural changes or quarterly. Generated by Hermes Agent v0.15.1.*
