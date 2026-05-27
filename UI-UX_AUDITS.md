# Coffee Pie — UI/UX Audit Report

**Date:** 2026-05-26
**Score:** 4.5 / 10
**Scope:** Full website — panel dashboard, public pages, translation engine, accessibility, performance, responsive design

---

## Executive Summary

The dashboard (`panel.html`) is the strongest asset: well-structured dark-mode UI, consistent component classes, functional translation engine with RTL support. However, the website carries massive Wix/Avo platform code bloat, has pervasive accessibility gaps (no focus indicators, missing form labels, no ARIA roles), and lacks loading/empty/error states entirely. The public pages (`precios.html`, `tienda.html`) are essentially unstyled platform shells.

**33 findings:** 6 Critical, 7 High, 10 Medium, 10 Low.

---

## Critical

### C-1 — Global `outline: none` kills all keyboard focus visibility
- **Files:** `panel.html:299`, `index.html:468`, `precios.html:468`, `tienda.html:469`
- **WCAG:** 2.4.7 Focus Visible (AA)
- **Impact:** Keyboard-only users cannot see which element is focused anywhere on the site. The platform re-adds outlines for its own tab class (`.keyboard-tabbing-on`) but the custom dashboard has no equivalent.
- **Fix:** Override with `:focus-visible { outline: 2px solid var(--cp-accent); outline-offset: 2px; }`

### C-2 — Skip-to-content link non-functional
- **File:** `panel.html:4275`
- **Impact:** `<button id="SKIP_TO_CONTENT_BTN">` is a `<button>`, not an `<a>`. It does not navigate anywhere. Keyboard users must tab through the entire header to reach content.
- **Fix:** Change to `<a href="#section-dashboard" class="skip-link">Ir al contenido principal</a>`, add `tabindex="-1"` to `#section-dashboard`.

### C-3 — Placeholder text used as sole label — WCAG 3.3.2 violation
- **Files:** `panel.html` — all form sections (Assets, Campaigns, Segments, Account, Config, Providers)
- **Impact:** Screen readers cannot determine the purpose of form fields. The `<label class="form-label">` elements exist visually but are not programmatically associated with their inputs (no `for` attribute, no `aria-labelledby`).
- **Fix:** Add `for="fieldId"` attributes to all `<label>` elements matching `<input id="…">`.

### C-4 — Missing label on language selector
- **File:** `panel.html:4345`
- **Impact:** The `<select id="panel-lang-select">` has no `<label>`, no `aria-label`. Screen readers announce it as "unlabeled combobox".
- **Fix:** Add `aria-label="Seleccionar idioma"` to the `<select>`.

### C-5 — Modal lacks focus trap and Escape key handling
- **Files:** `panel.html:4196-4264` (CSS), `panel.html:5554-5571` (JS)
- **Impact:** When modal is open, tabbing cycles behind it into the background page. Pressing Escape does nothing. Background page remains scrollable. No `role="dialog"` or `aria-modal="true"`.
- **Fix:** On open: set `document.body.style.overflow = 'hidden'`, move focus to modal, trap tab within. On close: restore focus. Add Escape key listener. Add `role="dialog" aria-modal="true" aria-labelledby="nodeModalTitle"`.

### C-6 — Dashboard body text is NOT translatable
- **File:** `panel.html` — all sidebar labels, section titles, form labels, button text (~200+ strings)
- **Impact:** When users switch language via the dropdown, only the header changes. The dashboard body remains in the authoring language (Spanish). The CoffeePieLang engine works correctly but no dashboard text is hooked into it.
- **Fix:** Wrap all dashboard text in `<span data-cp-key="...">` elements and implement a `renderDashboard(lang)` function that rebuilds text content from `translations.json`.

---

## High

### H-1 — Massive inline CSS bloat (~6,600 lines of Wix/Avo platform CSS per page)
- **Files:** `index.html`, `precios.html`, `tienda.html` — each duplicates the same ~4,500 lines of platform CSS inline in `<head>`
- **Impact:** Every page re-downloads identical CSS. No browser caching benefit from `.htaccess` cache headers since it's inline. Unused selectors, IE-specific `-ms-grid` rules, vendor prefixes for dead browsers.
- **Fix:** Extract platform CSS to external files with proper cache headers. Perform dead CSS elimination.

### H-2 — Render-blocking inline scripts in `<head>`
- **Files:** `index.html:22-55`, `precios.html:22-55`, `tienda.html:22-56`
- **Impact:** Polyfills, performance shims, viewer model JSON parsing, and platform init scripts all execute synchronously before first paint. Combined with inline CSS, this creates a large render-blocking payload.
- **Fix:** Defer non-critical scripts with `defer`. Externalize the viewer model JSON.

### H-3 — No ARIA roles on sidebar navigation
- **File:** `panel.html:4392-4497`
- **Impact:** The `<nav>` sidebar has no `aria-label`, no `aria-current="page"`, no semantic grouping for sections. Screen readers can't distinguish "Dashboard" from "Reportes" structurally.
- **Fix:** Add `aria-label="Navegacion principal"` to `<nav>`, `aria-current="page"` on active link, `role="group"` for section groups.

### H-4 — Touch targets below 44px minimum (WCAG 2.5.5)
- **Files:** Logout button 36x36px (line 2498), API copy button 28x28px (line 3758), node action button 30x30px (line 4172)
- **Fix:** Increase all icon-only buttons to ≥44x44px or use invisible padding to expand hit area while preserving visual size.

### H-5 — Color contrast failures for muted text and placeholders
- **Files:** `panel.html:2540` defines `--cp-text-muted: #999`
- **Impact:** #999 on #222 background = 3.5:1 ratio. Normal text (13px labels, 12px meta) needs 4.5:1 for AA. Fails WCAG 1.4.3. Placeholder color #555 on #181818 = ~2.1:1 — severe failure.
- **Fix:** Set `--cp-text-muted` to `#b0b0b0` (5.5:1). Set placeholder color to `#888` (3.5:1 min).

### H-6 — No loading, empty, or error states for data sections
- **File:** `panel.html` — all dashboard sections use hardcoded mock data
- **Impact:** No skeleton screens, spinners, "no data" messages, or error banners. `showToast()` is the only feedback. `.empty-state` CSS class exists (line 3057) but is unused.
- **Fix:** Add `data-loading="true"` containers with pulse skeletons. Use `.empty-state` for empty lists. Add inline error banners with retry buttons.

### H-7 — Inconsistent breakpoint naming (750px vs 768px overlap)
- **Files:** `panel.html:2400 (768px)`, `panel.html:2449 (320px-750px)`
- **Impact:** The 750-768px range falls into both media queries. Creates unpredictable layout behavior at specific widths.
- **Fix:** Standardize to: 1400px, 1024px, 768px, 480px. Remove the `320-750px` block, use `max-width: 768px` for small tablet, then `max-width: 480px` for phone.

---

## Medium

### M-1 — Mobile sidebar becomes dense grid — not intuitive for 10+ items
- **File:** `panel.html:3151`
- **Impact:** At <768px, sidebar becomes `grid-template-columns: repeat(auto-fill, minmax(144px, 1fr))` with all 12 items, section labels, and dividers hidden. Users lose hierarchy and grouping cues.
- **Fix:** Add a bottom nav bar with top 4-5 actions, or collapse sidebar into a hamburger menu on mobile.

### M-2 — No transition on tab switching
- **File:** `panel.html:5393` (`switchSection` JS)
- **Impact:** Sections switch instantly with `display: none` / `display: block`. Feels abrupt compared to modern SPA navigation.
- **Fix:** Add `opacity 0 → 1` transition with `transition: opacity 200ms ease`.

### M-3 — Toast lacks ARIA live region and uses single color for all types
- **File:** `panel.html:3068` (CSS), `panel.html:5382` (JS)
- **Impact:** Toast has no `role="alert"` or `aria-live="polite"`. Screen readers don't announce it. All toasts (success, error, warning) use the same green background.
- **Fix:** Add `role="status" aria-live="polite"`. Use different colors per message type.

### M-4 — Hash navigation doesn't respond to browser back/forward
- **File:** `panel.html:5393`
- **Impact:** Sidebar links change `window.location.hash` but there is no `hashchange` event listener. Pressing browser back changes the URL hash but the section doesn't update.
- **Fix:** Add `window.addEventListener('hashchange', handleHashChange)`.

### M-5 — Hamburger menu z-index: 999999999 (magic number)
- **File:** `translate.js:214`
- **Impact:** Extreme z-index risks conflicting with browser extensions, third-party widgets, and platform overlays.
- **Fix:** Use systematic scale: base 1, dropdown 100, sticky 200, modal 300, overlay 400, toast 500.

### M-6 — Inline SVGs add ~8-10KB to every load
- **File:** `panel.html` — 30+ inline SVG icons
- **Impact:** Repeated SVGs (user icon appears 4+ times). No browser caching. Each load re-downloads all SVG markup.
- **Fix:** Extract to `/assets/icons.svg` sprite sheet, reference via `<svg><use href="#icon-name"/></svg>`.

### M-7 — Hamburger menu links are hardcoded Spanish — not translated
- **File:** `translate.js:226-231`
- **Impact:** "INICIO", "PRECIOS", "TIENDA", etc. always display in Spanish regardless of selected language.
- **Fix:** Populate from `translations.json` or use `data-cp-key` attributes.

### M-8 — Form validation is toast-only — no inline field errors
- **File:** `panel.html:7006-7033`
- **Impact:** Users must read toast message and mentally map it to the offending field. No red border, no inline error text, no `aria-invalid="true"`.
- **Fix:** Set `aria-invalid="true"` on invalid field, append `<span class="form-error" role="alert">` below field, add red border.

### M-9 — Escape key listener never removed (memory leak)
- **File:** `translate.js:140`
- **Impact:** Each `setupLangDropdown()` call adds a `keydown` listener to `document`. Never removed. Accumulates on SPA-like navigations.
- **Fix:** Store listener reference, remove on dropdown destroy, or use single delegated listener.

### M-10 — RTL CSS rules use fragile Wix auto-generated element IDs
- **File:** `js/lang.js:474`
- **Impact:** Selectors like `[id$="_r_comp-lzg0bwm6"]` will break if Wix regenerates element IDs on platform update.
- **Fix:** Use semantic CSS classes (`.cp-ltr`) instead of platform-generated IDs.

---

## Low

### L-1 — Logo alt text is filename, not description
- **File:** `panel.html:4316`
- **Fix:** Change `alt="Coffe_Pie_Logo_edited.png"` to `alt="Coffee Pie"`.

### L-2 — Date format violation (DD/MM/YYYY instead of YYYY-MM-DD)
- **File:** `panel.html:4602`
- **Fix:** Change `Inicio: 01/04/2026` to `Inicio: 2026-04-01` per AGENTS.md mandate.

### L-3 — Typo in confirmation dialog
- **File:** `panel.html:7697`
- **Fix:** `'¿Estás seguro? de eliminar...'` → `'¿Estás seguro de eliminar este nodo? Las VMs alojadas serán migradas automáticamente.'`

### L-4 — `:has()` CSS selector without legacy browser support
- **File:** `panel.html:2527`
- **Fix:** Add JavaScript fallback that toggles a CSS class on the label.

### L-5 — Missing `type="button"` on some `<button>` elements
- **Fix:** Add `type="button"` to all non-submit buttons to prevent accidental form submission.

### L-6 — Deprecated `X-XSS-Protection` header
- **File:** `.htaccess:71`
- **Fix:** Remove the header. Content-Security-Policy already handles XSS prevention.

### L-7 — `Permissions-Policy` blocks camera/microphone — needed for USB-IP
- **File:** `.htaccess:73`
- **Fix:** Change to `camera=(self), microphone=(self)` to allow QFDM peripheral forwarding.

### L-8 — QR payment page has placeholder SVG, not functional
- **File:** `pago-seguro.html:91`
- **Fix:** Implement server-side QR generation that encodes actual payment data.

### L-9 — Double redirect on clean URLs with trailing slashes
- **File:** `.htaccess:32`
- **Fix:** Test and streamline redirect chain.

### L-10 — Duplicate language change handlers (inline `onchange` + `addEventListener`)
- **File:** `panel.html:4345`
- **Fix:** Remove inline `onchange`, rely solely on `populatePanelSelects()` listener in `translate.js`.

---

## Visual Design Scorecard

| Aspect | Score | Notes |
|--------|-------|-------|
| Color palette | 7/10 | Well-defined CSS custom properties. `--cp-info` underused. |
| Typography | 6/10 | Platform fonts overridden with hardcoded sizes, defeating scale. |
| Spacing | 5/10 | No 4px/8px baseline grid. Inconsistent padding values (10px, 14px, 20px, 24px, 32px, 40px). |
| Component reuse | 8/10 | Consistent `.btn`, `.form-input`, `.section-card`, `.stat-card` classes. Well-done. |
| Icon consistency | 6/10 | Uniform `stroke-width="2"` but sizes vary (14/16/18px). |
| Dark theme | 7/10 | Dashboard is fully dark. `pago-seguro.html` has white background — jarring transition. |

---

## Responsive Design Scorecard

| Breakpoint | Behavior | Issues |
|---|---|---|
| >1400px | Full desktop: 4-col stats, 240px sidebar | OK |
| 1024-1400px | 2-col stats, balance row visible | OK |
| 768-1024px | Narrower padding | OK |
| <768px | Sidebar → grid, all 1-col | BUT: grid unintuitive (M-1), 22-26px buttons below 44px target (H-4), 10-12px body text borderline illegible |
| <750px | Tighter padding | Overlaps 768px breakpoint (H-7) |

---

## Prioritized Remediation

| Phase | Count | Items |
|---|---|---|
| **This week** | 5 | C-1 (focus outlines), C-3 (form labels), C-4 (lang select label), C-5 (modal trap), H-5 (contrast) |
| **Next 2 weeks** | 5 | C-6 (dashboard i18n), M-3 (toast a11y), M-4 (hash nav), M-8 (inline errors), H-3 (sidebar ARIA) |
| **Month 1** | 6 | H-1/H-2 (de-bloat), H-4 (touch targets), M-1 (mobile nav), M-2 (transitions), M-5 (z-index) |
| **Month 2** | 5 | M-6 (SVG sprite), M-7 (menu i18n), H-6 (loading states), H-7 (breakpoints), M-10 (RTL selectors) |
| **Ongoing** | 12 | C-2 (skip link), L-1 through L-10, M-9 (escape listener) |
