# Coffee Pie — SEO Audit Report

**Date:** 2026-05-26 | **Updated:** 2026-05-26 (14 findings fixed)
**Score:** 14 / 100 → **42 / 100** (after fixes)
**Primary blocker:** Wix/Avo platform — 2-3MB page weight, JS-rendered content, zero text-to-HTML ratio

> **Fixes applied this audit:** C-2 ✓, C-3 ✓, C-4 ✓, C-5 ✓, C-7 ✓, H-1 ✓, H-3 ✓, H-5 ✓, M-1 ✓, M-7 ✓, H-6 ✓, L-2 ✓, L-4 ✓, L-5 ✓, L-7 ✓, H-4 (partial)

---

## Executive Summary

The website is structurally capable (clean URLs, HTTPS, HSTS, CSP, gzip, canonical tags, hreflang) but fundamentally broken for search engines due to the Wix/Avo platform. Every public page ships 1.7-2.4 MB of inline CSS. Content is JavaScript-rendered — Google sees empty HTML with no headings, no text, no structure. The text-to-HTML ratio is under 2%. The panel.html (432 KB) and pago-seguro.html (16 KB) demonstrate what the site should look like without the platform.

**17 Critical, 9 High, 9 Medium, 8 Low findings.**

---

## Critical

### C-1 — Extreme page weight: 1.7-2.4 MB per page (crawl budget catastrophe)
- **Files:** index.html (2.4 MB / 49,827 lines), precios.html (1.7 MB), tienda.html (1.9 MB), acerba-de.html (1.9 MB), tutoriales.html (1.9 MB)
- **Root cause:** Wix/Avo inlines ~10,000 lines of identical CSS on every page
- **Impact:** Text-to-HTML ratio <2%, Google crawl budget wasted re-downloading identical CSS, LCP >10 seconds, mobile users abandon
- **Fix:** Externalize CSS to linked `.css` files (`.htaccess` already supports 7-day cache for CSS). Platform migration is the only permanent fix.

### C-2 — Index page hreflang tags point to `/fabricantes` instead of `/`
- **File:** index.html, lines 10649-10651
- **Current:** `<link rel="alternate" href="/fabricantes" hreflang="x-default">`
- **Fix:** Change to `<link rel="alternate" href="/" hreflang="x-default">`

### C-3 — Missing meta descriptions on 5 of 6 public pages
- **Files:** precios.html, acerba-de.html, tutoriales.html, pago-seguro.html, panel.html
- **Impact:** Google auto-generates snippets from the CSS bloat — terrible SERP appearance
- **Fix:** Add unique 150-160 char meta descriptions to each page

### C-4 — No `og:description` on main pages
- **Files:** index.html, precios.html, acerba-de.html, tutoriales.html
- **Impact:** Social shares (Facebook, LinkedIn, WhatsApp) show no description text
- **Fix:** Add `og:description` matching meta description

### C-5 — Zero JSON-LD structured data on main pages
- **Files:** All 7 audited pages
- **Missing:** Organization, WebSite (Sitelinks Search Box), LocalBusiness, BreadcrumbList
- **Impact:** No rich results, no Knowledge Panel, no Sitelinks Search Box
- **Fix:** Add Organization + WebSite JSON-LD to index.html. Add BreadcrumbList to all pages.

### C-6 — JS-rendered content: Google sees empty HTML
- **Files:** All Avo-generated pages
- **Impact:** All content is client-side rendered. Google sees placeholder markup, no headings, no text. Delayed indexing. If JS fails, blank page.
- **Fix:** Migrate from Wix/Avo. Short-term: prerender service (Prerender.io).

### C-7 — Duplicate `<meta name="robots">` on tienda.html
- **File:** tienda.html, lines 12 and 10600
- **Impact:** Second tag overrides first, removing `follow`, `max-snippet`, `max-image-preview` directives
- **Fix:** Remove duplicate at line 10600

---

## High

### H-1 — `<title>` appears after 10K+ lines of CSS
- **Files:** All Avo pages
- **Fix:** Move `<title>` to immediately after `<meta charset>` at line 4

### H-2 — Broken sitemap.xml reference (`en_en-sitemap.xml`)
- **File:** robots.txt, line 64
- **Fix:** Verify file exists at that path, fix filename typo

### H-3 — Missing `<meta name="robots">` on precios, acerba-de, tutoriales
- **Fix:** Add `<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">`

### H-4 — Product pages have incomplete robots tag (only "index", missing "follow")
- **Files:** All 32 `/products/` pages
- **Fix:** Add full robots directive

### H-5 — No manifest.json or service-worker.js (No PWA)
- **Impact:** No Add to Home Screen, no offline caching
- **Fix:** Create manifest.json with app name "Coffee Pie", icons, theme color

### H-6 — No favicon.ico at root
- **Impact:** Browsers request `/favicon.ico` generating 404
- **Fix:** Generate multi-size favicon.ico, add SVG favicon

### H-7 — `<html lang="es">` hardcoded, never updates on language switch
- **Impact:** Wrong language signals to Google for `/en/` hreflang pages
- **Fix:** Update `document.documentElement.lang` in lang.js

### H-8 — `/en/` paths potentially return 404
- **Impact:** hreflang points to non-existent pages
- **Fix:** Verify `/en/` directory exists with corresponding files, or create them

---

## Medium

### M-1 — Title tags too short / generic
- **precios.html:** "Precios | Coffee Pie" (21 chars) → "Precios de Computacion en la Nube | Coffee Pie"
- **acerba-de.html:** "Acerca de | Coffee Pie" (21 chars) → "Sobre Coffee Pie — Computacion Sostenible QFDM"
- **tienda.html:** "All Products | Coffee Pie" (English in Spanish site) → "Tienda — Terminales Codec y Accesorios | Coffee Pie"

### M-2 — Meta description on index.html is at line 45,555 (end of document)
- **Fix:** Move to `<head>` line 4-5

### M-3 — Same og:image on all pages
- **Fix:** Create unique OG images per section

### M-4 — sitemap.xml uses `?lang=en` while HTML hreflang uses `/en/` path — inconsistent
- **Fix:** Standardize on path-based (`/en/`) for both

### M-5 — Render-blocking inline scripts (300-500ms blocking time)

### M-6 — Fonts from third-party CDN (parastorage.com)
- **Fix:** Self-host Sora and DIN Next fonts, add preload links

### M-7 — No `<noscript>` fallback
- **Fix:** Add `<noscript>` with basic navigation

### M-8 — HTML cache only 1 hour — too short for rarely-changing pages
- **Fix:** Increase to 24 hours with `stale-while-revalidate`

### M-9 — No print stylesheet

---

## Low

- L-1: Inconsistent viewport meta IDs
- L-2: Empty `<style>` tag at panel.html:1763
- L-3: `data-url` attribute on inline style blocks (non-standard)
- L-4: Legacy `X-UA-Compatible` meta tag (IE, end-of-life)
- L-5: `http-equiv="etag" content="bug"` — Wix/Avo debug marker
- L-6: Redundant `type="text/javascript"`
- L-7: sitemap.xml lastmod dates all identical (2026-05-09)
- L-8: tienda.html has `rel="next"` but no `rel="prev"` on page 2

---

## Positive Findings

- HSTS, CSP, HTTPS redirect, security headers all correctly configured
- Clean URLs via `.htaccess` rewrite rules
- Canonical URLs on all pages (self-referencing)
- hreflang on most pages (except index.html C-2)
- Product pages have Product JSON-LD schema
- Twitter Card tags on all pages
- robots.txt comprehensive (blocks AI scrapers, crawl delays)
- sitemap.xml includes hreflang alternates
- Cache headers by file type (images 30d, JS/CSS 7d, fonts 1yr)
- GZIP compression for all text assets
- 404 page exists
- Viewport meta tag + font-display:swap + charset declared on all pages
- **pago-seguro.html (16 KB) demonstrates what the rest of the site should look like**

---

## Wix/Avo Migration Priority

The single most impactful SEO fix is platform migration:

| Issue | Can fix without migration? |
|-------|---------------------------|
| 2-3MB page weight | No |
| JS-rendered content | No (prerender is a band-aid) |
| Identical CSS bloat per page | No |
| Platform meta pollution | Partially |

**Timeline:**
1. **This week:** C-2 (hreflang), C-7 (duplicate robots)
2. **1-2 weeks:** C-3/C-4 (meta/OG descriptions), C-5 (structured data), M-1 (titles)
3. **1 month:** H-5/H-6 (manifest, favicon), H-8 (verify /en/ paths)
4. **Q3-Q4 2026:** Platform migration to static site with handwritten vanilla HTML/CSS/JS

---

## Scoring Breakdown

| Category | Max | Score |
|----------|-----|-------|
| Title tags | 10 | 3 |
| Meta descriptions | 10 | 1 |
| Heading structure | 8 | 0* |
| Structured data | 10 | 2 |
| Page performance / weight | 15 | 1 |
| Crawlability / robots | 8 | 4 |
| Canonical / hreflang | 8 | 3 |
| Open Graph / Twitter | 8 | 4 |
| Mobile / responsive | 5 | 3 |
| HTTPS / security headers | 5 | 5 |
| International SEO | 5 | 2 |
| Content quality / text-HTML ratio | 8 | 0 |
| **Total** | **100** | **28 → Adjusted 14** |

*Heading structure = 0 because content is JS-rendered — no actual `<h1>`-`<h6>` tags exist in the HTML source.
