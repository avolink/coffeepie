# Coffee Pie Website Frontend - Deep Audit

**Date:** 2026-06-05
**Scope:** `/home/avolink/DEV/coffeepie/coffeepie_website/`
**Auditor:** Hermes Agent (automated)

---

## 1. SECURITY AUDIT — Score: 45/100

### 1.1 XSS Vulnerabilities (CRITICAL)

The codebase makes extensive use of `innerHTML` with template literals that interpolate user-controlled or localStorage-derived data without ANY sanitization.

| File | Line(s) | Risk | Detail |
|------|---------|------|--------|
| `public/js/cart.js` | 68-69 | **HIGH** | `svg.innerHTML = \`...${squarishCartPaths}...\`` — squarishCartPaths is hardcoded SVG, lower risk but pattern is dangerous |
| `public/js/cart.js` | 169-175 | **HIGH** | `container.innerHTML = \`...\`` — empty cart HTML has no user data, but opens door |
| `public/js/cart.js` | 268-294 | **CRITICAL** | `itemsHtml += \`...${item.name}...${item.image}...${item.variant}...\`` — **item.name, item.image, and item.variant come from localStorage (cart data) and are inserted raw into innerHTML**. An attacker who can modify localStorage (e.g., via another tab or browser extension) can inject arbitrary HTML/scripts. |
| `public/js/cart.js` | 297-540 | **CRITICAL** | `container.innerHTML = \`...${itemsHtml}...${total.toLocaleString()}...\`` — total is safe, but itemsHtml carries unsanitized user data from above. |
| `public/assets/cart.js` | 131, 147-173, 176 | **CRITICAL** | Same pattern — duplicate file with same vulnerability |
| `public/js/vanilla-gallery.js` | 56, 76, 93, 124, 163, 185 | **MEDIUM** | innerHTML with translated strings — data sourced from products.json (trusted JSON), so risk is lower but pattern is indiscriminate |
| `public/translate.js` | 80, 189, 194, 243 | **LOW-MEDIUM** | innerHTML with language flag SVGs and locale codes — locale codes come from hardcoded LANGUAGES array, low risk |
| `public/header.js` | 52 | **MEDIUM** | `wrapper.innerHTML = html` where html is the response from `fetch('/header.html')` — if header.html is ever compromised or an attacker can MitM (despite HTTPS), this is XSS |
| `public/js/ads-login.js` | 53 | **LOW** | innerHTML with hardcoded HTML strings, no user data |
| `public/panel.html` | 7117, 7331, 7472, 7820, 7827, 7881, 7945-7982, 8112 | **HIGH** | Multiple innerHTML injections with API response data for nodes, maintenance windows, API keys table — **data sourced from backend API responses is rendered via innerHTML without sanitization** |
| `public/secure-payment.html` | 211, 218, 229, 244, 267 | **HIGH** | Cart data from localStorage rendered via innerHTML — same issue as cart.js |
| `public/index.html` | 8276 | **LOW** | Video play/pause icon toggle — hardcoded SVG, low risk |
| `public/404.html` | 40410 | **LOW** | `missedUrls.map(url => \`<li>${url}</li>\`)` — URL from window.location, used as list item text (not HTML context injection), low risk |
| `public/assets/economia-circular.html` | 162, 170 | **MEDIUM** | innerHTML with data items |

**Recommendation:** Sanitize ALL user-controlled data before inserting into innerHTML using `textContent` for text nodes, or a lightweight HTML escaping function. At minimum, escape `<`, `>`, `"`, `'`, and `&` characters in all cart item fields (name, image URL, variant).

### 1.2 CSRF Protection — None

| Finding | Detail |
|---------|--------|
| No CSRF tokens | No forms have CSRF tokens. The login form in `ads-login.js` sends via XHR without CSRF headers. The checkout button in cart.js navigates to `/secure-payment` without any CSRF protection. |
| Recommendation | Implement CSRF tokens on all state-changing forms/endpoints. Use the `SameSite=Strict` cookie attribute as a baseline defense. |

### 1.3 localStorage Usage — Tampering Risk (MEDIUM)

| File | Line(s) | Risk |
|------|---------|------|
| `public/js/cart.js` | 10, 21 | **MEDIUM** — Cart data (items, quantities, prices) stored in `localStorage` under `coffee_pie_cart`. This is client-side mutable — users can modify prices, quantities, add fraudulent items. If the backend trusts cart data from localStorage without server-side validation/recalculation, this enables price manipulation attacks. |
| `public/js/lang.js` | 29, 599, 612 | **LOW** — Language preference stored in localStorage, no security impact |
| `public/translate.js` | 49, 56 | **LOW** — Language preference (duplicate key `cp_lang`) |
| `public/404.html` | 40395-40427 | **LOW** — 404 URL logging, minor privacy concern |
| `public/secure-payment.html` | 156, 185, 193 | **HIGH** — Cart data read from localStorage to calculate payment totals. If the backend doesn't independently recalculate prices, this is exploitable. |
| `public/pricing.html` | 30797, 30814 | **MEDIUM** — Cart manipulation on pricing page |

**Recommendation:** Never trust client-side cart prices. Always recalculate totals server-side using authoritative product prices from the database. Client-side cart should only be used for UI rendering.

### 1.4 Firebase Configuration Exposure

| File | Finding |
|------|---------|
| `public/js/firebase-init.js` | Line 9: `apiKey: "YOUR_FIREBASE_API_KEY"` — **placeholder value, not a real key.** Good. Line 14: `appId: "1:194088927708:web:7f6d34ea76aa4694b7c7128f"` — **REAL App ID exposed**. While Firebase App IDs are not secret, they do expose the project identity. Line 24: `'6Ld_RECAPTCHA_ENTERPRISE_SITE_KEY'` — **placeholder**. Good practice. Lines 10-13: Real project identifiers (`coffeepie-firebase` project ID, auth domain, messaging sender ID, storage bucket) — all exposed. These are not secrets per se, but they reveal infrastructure. |
| `public/assets/firebase-init.js` | **Duplicate file** with same content — two copies to maintain |

**Recommendation:** The Firebase config is mostly placeholder, which is correct. The App ID, project ID, and messaging sender ID are publicly visible in every Firebase web app by design and are not secret. However, ensure Firebase Security Rules are properly configured server-side.

### 1.5 CSP Compliance

| Location | Finding |
|----------|---------|
| `.htaccess` line 80 | `Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://www.gstatic.com https://static.parastorage.com https://static.avostatic.com https://www.youtube.com https://s.ytimg.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data: https://static.parastorage.com; connect-src 'self' https:; frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; frame-ancestors 'self'; base-uri 'self'; form-action 'self'` |
| Assessment | **ADEQUATE baseline** but has weaknesses: |
| | - `'unsafe-inline'` for scripts — necessary because cart.js, lang.js, vanilla-gallery.js inject inline `<style>` blocks and use inline `onclick`/`onchange` event handlers. This weakens XSS protection significantly. |
| | - `'unsafe-inline'` for styles — required for the same reason (dynamic style injection in cart.js) |
| | - `img-src ... https:` — allows images from any HTTPS origin. Could be tightened. |
| | - `connect-src ... https:` — allows connections to any HTTPS host. Too broad. |
| | - No `require-trusted-types-for 'script'` directive |
| | - **Missing from firebase.json** — CSP is only in `.htaccess` (Apache). Firebase Hosting does not use `.htaccess`. The CSP header is **NOT applied when deployed to Firebase Hosting**. |
| `firebase.json` | No CSP headers configured. Only X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, HSTS, Permissions-Policy. **The CSP from .htaccess is NOT being served.** |
| `coffeepie.conf` | Nginx config also **missing CSP headers entirely**. |

**Recommendation:** 
1. Move CSP headers from `.htaccess` into `firebase.json` headers section (Firebase Hosting is the primary deploy target).
2. Add CSP to `coffeepie.conf` for Nginx deployments.
3. Refactor inline event handlers (`onclick`, `onchange`) to use `addEventListener` to allow removing `'unsafe-inline'` from script-src.
4. Tighten `connect-src` to specific domains.
5. Add `require-trusted-types-for 'script'` once inline scripts are eliminated.

### 1.6 Third-Party Scripts — No SRI Hashes

| Script Source | Used In |
|---------------|---------|
| `https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js` | firebase-init.js line 5 |
| `https://www.gstatic.com/firebasejs/10.8.0/firebase-app-check.js` | firebase-init.js line 6 |
| `https://static.parastorage.com` / `https://static.avostatic.com` | Avo/Wix platform scripts (in CSP, loaded by Avo pages) |
| `https://www.youtube.com` / `https://s.ytimg.com` | YouTube embeds |

**No `integrity` attributes on ANY third-party script or stylesheet.** This means if gstatic.com is compromised, Firebase JS could be replaced with malicious code.

**Recommendation:** Add SRI hashes to all third-party `<script>` and `<link>` tags. For Firebase 10.8.0:
- `firebase-app.js` integrity: `sha384-...` (generate from the actual file)
- `firebase-app-check.js` integrity: `sha384-...`

### 1.7 Hardcoded Secrets / API Keys

| Finding | Detail |
|---------|--------|
| `firebase-init.js` line 9 | `apiKey: "YOUR_FIREBASE_API_KEY"` — placeholder, **no real key exposed**. ✅ |
| `firebase-init.js` line 24 | `'6Ld_RECAPTCHA_ENTERPRISE_SITE_KEY'` — placeholder. ✅ |
| `ads-login.js` line 6 | `ORCHESTRATOR_URL = 'https://orquestador.coffeepie.co'` — hardcoded backend URL. Not a secret, but configuration should be externalized. |
| `panel.html` | API key management UI — no keys hardcoded in frontend. ✅ |
| **No secrets found exposed.** | The project follows AGENTS.md rule: "NEVER commit secrets, tokens, or credentials". ✅ |

### 1.8 Other Security Concerns

| Finding | Location | Detail |
|---------|----------|--------|
| postMessage to wildcard origin | `translate.js` line 62 | `iframe.contentWindow.postMessage({...}, '*')` — broadcasts language change to ALL iframes regardless of origin. Should specify target origin. |
| No HTTPS enforcement in Nginx | `coffeepie.conf` | Nginx config only has `listen 80`, no `listen 443 ssl` or redirect. Apache `.htaccess` has HTTPS redirect (line 16-17), but Nginx does not. |
| X-XSS-Protection deprecated | `.htaccess` line 77, `firebase.json` line 110 | `X-XSS-Protection: 1; mode=block` is deprecated and can cause security issues in older browsers. The CSP header is the modern replacement. |

---

## 2. CODE QUALITY — Score: 52/100

### 2.1 Duplicate Files (MAJOR)

| Duplicate Pair | Detail |
|----------------|--------|
| `public/js/cart.js` (1130 lines) vs `public/assets/cart.js` (511 lines) | **TWO DIFFERENT VERSIONS** of cart functionality. `js/cart.js` is the newer, more feature-complete version (has product URL matching, product selectors, accordion, translated toast). `assets/cart.js` is a stripped-down older version. Both define the same global functions (`getCart`, `saveCart`, `updateQty`, `setQty`, `removeFromCart`, `updateCartUI`, `renderCartPage`). If both are loaded, behavior is undefined. |
| `public/js/product-accordion.js` vs `public/assets/product-accordion.js` | **Identical content** (134 lines each). Wasteful duplication. |
| `public/js/firebase-init.js` vs `public/assets/firebase-init.js` | **Identical content**. Duplicate. |
| `public/translations.json` vs `public/translations.json.bak_20260527` | Backup file in public directory — **deployable to production**. Should be moved out of public/. |

**Recommendation:** Consolidate. Delete `public/assets/cart.js` (use `js/cart.js`), delete `public/assets/product-accordion.js`, delete `public/assets/firebase-init.js`. Move `.bak` files out of public/.

### 2.2 Console.log Statements in Production (58 found)

| File | Count |
|------|-------|
| `public/js/cart.js` | 15 |
| `public/js/ads-login.js` | 8 |
| `public/translate.js` | 7 |
| `public/assets/product-accordion.js` | 6 |
| `public/js/product-accordion.js` | 6 |
| `public/assets/cart.js` | 6 |
| `public/assets/base.js` | 5 |
| `public/js/firebase-init.js` | 1 |
| `public/assets/firebase-init.js` | 1 |
| `public/index.html` | 1 |
| Others | 2 |

**Total: 58 console.log/console.warn/console.error statements.** These should be stripped in production builds. At minimum, all `console.log` (debug/info level) should be removed; `console.warn` and `console.error` may be kept for legitimate error reporting.

### 2.3 JavaScript Issues

| Issue | File | Line | Detail |
|-------|------|------|--------|
| Unused variable | `js/cart.js` | 137 | `let hideChildren = true;` — declared but never read after assignment. |
| Duplicate DOMContentLoaded listener | `js/cart.js` | 105-108 vs 934-937 | Both listeners do identical work (`a[href*="cart-page"]` → `/cart.html`, `updateCartUI()`). The second at line 934 is a duplicate. |
| Double init | `js/cart.js` | 671-672 | `initQuantityButtons` registered on both `DOMContentLoaded` and `load` events — causes it to run twice. |
| Inconsistent variable declarations | `js/cart.js` | 118 | `var cleanContainer` mixed with `const`/`let` in the same function. |
| Missing null guard | `js/cart.js` | 94 | `el.offsetWidth > 100` — no check that `el` exists before accessing `.offsetWidth`. Works because querySelector returns null, but `document.querySelector(sel)` in forEach could be null. Actually, the for...of iterates over results, so `el` is always defined. However offsetWidth can fail on detached elements. |
| Mixed Spanish/English variable names | Multiple | `CART_STORAGE_KEY` (English) vs `STORAGE_KEY` (English) vs `cp_lang` vs `coffee_pie_cart` — inconsistent naming. `cp_lang` in translate.js vs `cp_lang` in lang.js vs `coffee_pie_lang` in 404.html — **three different localStorage keys for language preference**. |
| parsePrice fragility | `js/cart.js` | 28-46 | Removes ALL dots then converts comma to dot. This breaks for prices like "1.200.000,00" (correctly handled: becomes 1200000.00) but would fail for "1,200,000.00" (English format). The apostrophe format "400'000" works but the `replace(/\./g, '')` step would incorrectly strip a decimal dot if no comma was present. |
| Implicit global | `translate.js` | 1 | `console.log('[CoffeePie] translate.js starting...');` — top-level code outside any function/IIFE in a non-module script. |

### 2.4 HTML Validation Issues

| Issue | File | Detail |
|-------|------|--------|
| Duplicate `<style>` blocks | All product pages (e.g., `products/terminal-codec-commander-basic-by-coffee-pie.html` lines 19-31) | Every product page has identical `:root` CSS variables block. Should be extracted to shared CSS. |
| Template placeholder | `products/template.html` line 79 | `PRODUCT_DATA_PLACEHOLDER` — not valid JavaScript. This template is not directly deployable. |
| Typo in product name | `products.json` line 188 | `"Adapdator WiFi by TP-Link"` — should be "Adaptador" |
| `font-size: 10px` on body | `panel.html`, `header.css`, `css/producto.css` | This is an Avo/Wix convention that makes all `rem` values 10x smaller than expected. Forces all pages to work around it with explicit font-size overrides. |
| Viewport meta inconsistency | `panel.html` line 6 | `id="avoDesktopViewport"` — non-standard `id` on viewport meta tag |
| Non-standard meta tags | `panel.html` lines 43-46 | `X-Avo-Meta-Site-Id`, `X-Avo-Application-Instance-Id`, `X-Avo-Published-Version`, `etag: "bug"` — proprietary Avo platform metadata leaking into public HTML |

### 2.5 CSS Duplication

| Issue | Detail |
|-------|--------|
| `header.css` | 5338 lines — mostly auto-extracted Avo styles. Many rules are redundant with the inline styles in `panel.html` and `index.html`. |
| `panel.html` | 8148 lines — massive inline CSS (453KB). This is Avo platform CSS that should be in external files for caching. |
| `css/producto.css` | 202 lines — well-organized, minimal duplication. ✅ |
| `footer.css` | Exists but needs review |
| `cart.js` inline styles | The cart page injects ~200 lines of CSS via innerHTML (lines 298-484). This CSS is never cached. |
| Duplicate `:root` variables | Every product HTML page and `header.css` define the same CSS custom properties. |

---

## 3. STRUCTURE / COHERENCE — Score: 55/100

### 3.1 Page Consistency

| Page Group | Header | Footer | CSS | Notes |
|------------|--------|--------|-----|-------|
| Avo-generated pages (index.html, pricing.html, about.html, tutorials.html, api.html, etc.) | Integrated via Avo platform (not reusable-header) | Integrated via Avo | Inline CSS from Avo | Consistent within group |
| Standalone pages (store.html, cart.html) | `reusable-header-placeholder` + `header.js` | `reusable-footer-placeholder` + `footer.js` | Inline `<style>` reset + external CSS | Consistent |
| Product pages (products/*.html) | `reusable-header-placeholder` + `header.js` | `reusable-footer-placeholder` + `footer.js` | `/css/producto.css` | Consistent ✅ |
| panel.html | Embedded in Avo platform | N/A | Massive inline CSS | Different layout entirely |
| 404.html | Avo | Avo | Inline | Different |
| secure-payment.html | `reusable-header-placeholder` | `reusable-footer-placeholder` | Inline | Standalone |
| assets/economia-circular.html | Unknown | Unknown | Inline | Standalone section |

**Finding:** Three different header/footer systems exist: (1) Avo native, (2) reusable-header injection via header.js, (3) panel.html embedded. This is mostly by design (Avo platform pages vs vanilla pages) but creates maintenance burden.

### 3.2 translations.json Key Matching

- **24151 lines, 2.2 MB** — very large translation file
- Keys use dot notation (e.g., `"top of page"`, `"Ir al contenido principal"`)
- `lang.js` does reverse lookup: normalizes Spanish text and searches Map for matching entry — this means **translations work for any text on the page that matches a key**, regardless of whether the key was intentionally coded
- **Risk:** If two elements have the same Spanish text but need different translations, the first match wins. This is inherent to the reverse-lookup design.
- The `GROUP_SEPARATOR = ' ||| '` approach for multi-paragraph translation is fragile — if the original text format changes, translations break silently.

### 3.3 File Reference Audit

| Referenced File | Exists? | Notes |
|-----------------|---------|-------|
| `/header.js` | ✅ | Injected on all standalone pages |
| `/header.css` | ✅ | Loaded dynamically by header.js |
| `/js/lang.js` | ✅ | Loaded dynamically by header.js |
| `/translate.js` | ✅ | Loaded dynamically by header.js |
| `/js/cart.js` | ✅ | Referenced by store.html, cart.html, all product pages |
| `/js/firebase-init.js` | ✅ | Referenced by index.html, all product pages |
| `/js/vanilla-gallery.js` | ✅ | Referenced by store.html |
| `/footer.js` | ✅ | Referenced by store.html, cart.html, product pages |
| `/footer.css` | ✅ | Exists |
| `/css/vanilla-gallery.css` | ❓ | Referenced by store.html (line 11) — needs verification |
| `/css/producto.css` | ✅ | Referenced by all product pages |
| `/assets/avo/css/main.68f9276d.min.css` | ✅ | Avo platform CSS (cache-busted filename) |
| `/translations.json` | ✅ | 2.2 MB, loaded via XHR |
| `/data/products.json` | ✅ | 233 lines, 30 products |
| `footer.html` (fetched via JS) | ✅ | Header/footer HTML |
| `header.html` (fetched via JS) | ❓ | Needs verification — not in initial file listing |
| `/assets/Coffe_Pie_Logo_edited(1).png` | ❓ | Referenced in footer.html |
| `/assets/avo/media/it-specialist.mp4` | ❓ | Referenced in footer.html |
| `/secure-payment` (checkout button) | ✅ | firebase.json redirects to `/secure-payment.html` |

### 3.4 URL Naming Consistency

| Spanish | English | Notes |
|---------|---------|-------|
| `/precios` → `/pricing.html` | `/pricing` → `/pricing.html` | Both work via rewrites ✅ |
| `/tienda` → `/store.html` | `/store` → `/store.html` | Both work ✅ |
| `/carrito` → `/cart.html` | `/cart` → `/cart.html` | Both work ✅ |
| `/acerca-de` → `/about.html` | `/about` → `/about.html` | Both work ✅ |
| `/productos` → 301 to `/products` | `/products` → (cleanUrl to .html) | Spanish redirects to English ✅ |
| `/tutoriales` → `/tutorials.html` | `/tutorials` → `/tutorials.html` | Both work ✅ |
| `/panel` | No separate Spanish URL | Only English |
| `/api` | No separate Spanish URL | Only English |

**Issues:**
- `coffeepie.conf` uses OLD Spanish URLs like `/tienda.html`, `/precios.html`, `/acerca-de.html` that don't match the current English-first URL strategy
- `coffeepie.conf` is missing MANY rewrites present in `firebase.json` (e.g., `/store`, `/pricing`, `/investor-portal`, `/cloud-providers`, `/manufacturers`, `/secure-payment`, `/cart`, and their Spanish equivalents)
- The `.htaccess` has `/princing` → `/pricing` redirect but `firebase.json` also has `/princing` → `/pricing` (duplicated, but harmless)

### 3.5 Product Pages vs products.json Alignment

| products.json slug | HTML file exists? | Data Match |
|--------------------|-------------------|------------|
| `terminal-codec-commander-pro-by-coffee-pie` | ✅ | ✅ |
| `terminal-codec-commander-basic-by-coffee-pie` | ✅ | ✅ |
| `terminal-codec-commander-core-by-coffee-pie` | ✅ | ✅ |
| `hot-swappable-battery-for-commander-by-powerowl` | ✅ | ✅ |
| `low-profile-keycaps-set-for-commander` | ✅ | ✅ |
| `custom-keycaps-set-for-commander-by-womier` | ✅ | ✅ |
| `custom-keycaps-set-for-commander-by-lofree` | ✅ | ✅ |
| `tpe-optomechanical-switches-by-coffee-pie` | ✅ | ✅ |
| `optomechanical-switches-for-commander-by-keychron` | ✅ | ✅ |
| `optomechanical-switches-for-commander-by-razer` | ✅ | ✅ |
| `low-profile-stabilizers-set-for-commander-by-cherry` | ✅ | ✅ |
| `audio-expansion-card-by-framework` | ✅ | ✅ |
| `usb-c-expansion-card-by-framework` | ✅ | ✅ |
| `usb-a-expansion-card-by-framework` | ✅ | ✅ |
| `displayport-expansion-card-by-framework` | ✅ | ✅ |
| `hdmi-expansion-card-by-framework` | ✅ | ✅ |
| `micro-sd-expansion-card-by-framework` | ✅ | ✅ |
| `sd-expansion-card-by-framework` | ✅ | ✅ |
| `storage-expansion-card-250gb-by-framework` | ✅ | ✅ |
| `storage-expansion-card-1tb-by-framework` | ✅ | ✅ |
| `rj45-to-sfp-optical-fiber-converter-by-xicom` | ✅ | ✅ |
| `ethernet-rj45-adapter-by-tp-link` | ✅ | ✅ |
| `wifi-and-bluetooth-adapter-by-ugreen` | ✅ | ✅ |
| `wifi-adapter-by-tp-link` | ✅ | ✅ |
| `touchpad-module-by-framework` | ✅ | ✅ |
| `numpad-module-for-commander-by-framework` | ✅ | ✅ |
| `commander-keyboard-cover` | ✅ | ✅ |
| `commander-base-heatsink` | ✅ | ✅ |
| `commander-back-io-panel` | ✅ | ✅ |
| `template.html` | ✅ | Template, not a product — contains `PRODUCT_DATA_PLACEHOLDER` |

**All 30 products in `products.json` have corresponding HTML files.** ✅ However, each product page duplicates the product data as inline JSON (e.g., line 79 of the Basic Commander page). This means updating a price requires editing both `products.json` AND the individual HTML file.

The cart.js `renderCartPage` function has a massive if-else chain (lines 203-265) to map product names back to URLs. This is fragile and duplicates data. Recommendation: use a Map or products.json lookup instead.

### 3.6 cart.js / store.html / cart.html Coherence

- `store.html` loads `vanilla-gallery.js` which reads `products.json` and renders the product grid — works ✅
- `cart.html` loads `cart.js` which reads cart from localStorage and renders it — works ✅
- `cart.html` has `#cart-container` and cart.js looks for `#cart-container` when `#custom-cart-root` is not found — works ✅
- `cart.js` updateCartUI updates cart icon badges and SVG — works with both Avo and vanilla pages ✅
- The "add to cart" click handler in cart.js (lines 683-932) supports Avo product pages (with `data-hook="product-item-root"`) and vanilla product pages (looking for `h1`, JSON-LD, etc.) — ambitious but fragile.

---

## 4. PERFORMANCE — Score: 48/100

### 4.1 Page Weight Analysis

| File | Size | Issue |
|------|------|-------|
| `translations.json` | **~2.2 MB** (24151 lines) | Loaded via blocking XHR by `lang.js` on every page. This is the single biggest performance problem. The entire translation dictionary for 12 languages is downloaded even if the user only needs one. |
| `panel.html` | **~453 KB** (8148 lines) | Massive inline CSS. Should be external for caching. |
| `index.html` | Unknown but likely similar to panel.html | Avo-generated, heavy inline CSS |
| `header.css` | **~167 KB** (5338 lines) | Large but loaded once and cached |
| `cart.js` | **~50 KB** (1130 lines) | Moderately large but acceptable for functionality |

**Total per-page load for product pages:**
- translations.json: 2.2 MB
- cart.js: 50 KB
- producto.css: 5 KB
- header.js: 2.7 KB
- header.css: 167 KB (cached after first load)
- lang.js: 24 KB
- translate.js: 18 KB
- firebase-init.js: 1.3 KB
- footer.js + footer.css: unknown

**~2.5 MB** for first visit to a product page (assuming cache miss on translations.json). After cache: ~100 KB.

### 4.2 Image Optimization

- **No evidence of responsive images** — no `<picture>` elements, no `srcset`, no `sizes` attributes found
- **Only one image uses `loading="lazy"`** — the footer logo in `footer.html` (line 50). Product hero images use `loading="eager"`.
- **Image formats mixed:** `.png`, `.jpg`, `.webp` — WebP is good but not universally used
- **No AVIF images** despite having it in the Cache-Control header
- **Product images in products.json** reference `/assets/avo/downloads/` URLs — these are likely served through Avo's CDN with optimization, but no local optimization exists
- **Missing image dimensions** — no `width`/`height` attributes on most `<img>` tags to prevent layout shift (CLS)

### 4.3 JavaScript Bundle Analysis

| Script | Load Strategy | Blocking? |
|--------|--------------|-----------|
| `header.js` | `defer` | Non-blocking ✅ |
| `footer.js` | None (synchronous) | **Blocking** — at end of body so minimal impact |
| `cart.js` | `defer` (product pages), synchronous (cart.html) | Mixed — `defer` is good, synchronous at end of body is acceptable |
| `lang.js` | Dynamically injected by header.js | Async ✅ |
| `translate.js` | Dynamically injected by header.js | Async ✅ |
| `firebase-init.js` | `defer` (product pages), `type="module"` (index.html) | `defer` is fine, `type="module"` is deferred by default ✅ |
| `vanilla-gallery.js` | Synchronous (store.html) | **Blocking** — should use `defer` |

### 4.4 Caching Strategy

| Resource | Cache Duration | Assessment |
|----------|---------------|------------|
| Images | 30 days (`max-age=2592000, immutable`) | Good ✅ |
| JS/CSS | 7 days (`max-age=604800`) | Could be longer if versioned/fingerprinted. Without cache-busting, 7 days means updates may take a week to reach users. |
| Fonts | 1 year (`max-age=31536000, immutable`) | Good ✅ |
| HTML | 1 hour (`max-age=3600, must-revalidate`) | Reasonable for dynamic content ✅ |
| `translations.json` | Not explicitly cached | JSON files are not covered by any cache rule. With a 2.2 MB payload, this is a major gap. |

### 4.5 Lazy Loading

- Footer video uses `preload="auto"` — should be `preload="none"` or `preload="metadata"` to avoid unnecessary bandwidth
- No lazy loading for below-fold product images
- No intersection observer for deferred content loading
- Translations.json loads eagerly even though translation may not be needed for Spanish-speaking users (default language)

---

## 5. ADDITIONAL FINDINGS

### 5.1 Configuration Drift

| Config | Status |
|--------|--------|
| `firebase.json` | Primary deploy config. Has 27 rewrites, full header set (except CSP), cleanUrls enabled. ✅ |
| `.htaccess` | Apache config. Has CSP, HTTPS redirect, rewrites. Partially duplicated from firebase.json. Has `/princing` redirect that firebase.json also has. **Missing all English URL rewrites** (no `/store`, `/pricing`, `/cart`, etc.). |
| `coffeepie.conf` | Nginx config. **Severely outdated** — uses old Spanish filenames (`/tienda.html`, `/precios.html`, `/acerca-de.html`), missing CSP, missing HTTPS, missing most rewrites. |

The three configurations are inconsistent and would produce different behavior depending on the deployment target.

### 5.2 Avo/Wix Platform Artifacts

The `public/assets/` directory contains Wix/Avo platform leftovers:
- `cast_sender(1).js` — Chromecast sender (YouTube-related)
- `browser-deprecation.bundle.es5.js` — legacy browser detection
- `bottomPlaceholder.js`, `detailsPlaceholder.js`, `colorPickerUrlFragment.js` — Avo web components
- YouTube iframe HTML files (`Lc4-2cVKxp0.html`, `h1wpuAjutzY.html`, `U4Sqh-uJ2NA.html`)
- `base.js` — YouTube player infrastructure (6193+ lines)

These files may be necessary for the Avo platform pages but are dead weight for standalone vanilla pages.

### 5.3 Accessibility Issues

- Footer video autoplays with `autoplay` attribute — should respect `prefers-reduced-motion`
- No skip-to-content link on many pages
- Cart quantity inputs have no accessible labels (only `aria-label` on buttons)
- Language dropdown uses `role="option"` but is not inside a `role="listbox"` parent consistently
- `:focus-visible` styles exist (header.css line 303-306) ✅ but not consistently applied

### 5.4 SEO Issues

- `cart.html` has `robots: noindex, nofollow` — correct ✅
- `panel.html` has `robots: noindex, nofollow` — correct ✅
- Product pages have proper meta tags and canonical URLs ✅
- `sitemap.xml` and `en_en-sitemap.xml` exist ✅
- 404 page tracking localStorage writes for every 404 — minor but could accumulate

---

## 6. SCORECARD

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Security | 45/100 | 0.35 | 15.75 |
| Code Quality | 52/100 | 0.25 | 13.00 |
| Structure / Coherence | 55/100 | 0.25 | 13.75 |
| Performance | 48/100 | 0.15 | 7.20 |

**OVERALL SCORE: 50/100**

---

## 7. PRIORITIZED RECOMMENDATIONS

### CRITICAL (Fix Immediately)
1. **Sanitize all innerHTML insertions of user-controlled data** — especially cart item names, images, and variants in `cart.js` and `secure-payment.html`. Escape HTML entities or use `textContent` for text.
2. **Add CSP headers to Firebase Hosting** (`firebase.json`) — the current CSP only exists in `.htaccess` which is not used by Firebase.
3. **Never trust client-side cart prices** — backend must recalculate totals from authoritative product database.

### HIGH (Fix This Sprint)
4. **Consolidate duplicate files** — delete `public/assets/cart.js`, `public/assets/product-accordion.js`, `public/assets/firebase-init.js`.
5. **Strip console.log statements** from production code (58 instances).
6. **Split translations.json** — load only the user's language + fallback. 2.2 MB is too large.
7. **Update `coffeepie.conf`** to match current URL strategy in `firebase.json`.
8. **Add SRI hashes** to Firebase JS imports.

### MEDIUM (Fix Next Sprint)
9. **Refactor inline event handlers** (`onclick`, `onchange`) to `addEventListener` to enable removing `'unsafe-inline'` from CSP.
10. **Add lazy loading** to product images below the fold.
11. **Cache translations.json** — add explicit cache headers for JSON files.
12. **Fix the duplicate DOMContentLoaded listener** in cart.js (line 934).
13. **Remove `public/translations.json.bak_20260527`** from public directory.
14. **Fix typo** "Adapdator" in products.json line 188.

### LOW (Backlog)
15. **Generate product pages from template** instead of duplicating product data inline.
16. **Reduce header.css** — many rules are Avo platform remnants unused by vanilla pages.
17. **Standardize localStorage keys** — three different keys for language preference (`cp_lang`, `coffee_pie_lang`).
18. **Specify `postMessage` target origin** in translate.js.
19. **Add `prefers-reduced-motion`** media query for footer video autoplay.
20. **Fix `coffeepie.conf`** to include HTTPS redirect and CSP headers.
