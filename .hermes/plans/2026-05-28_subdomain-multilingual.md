# Multilingual Subdomain Architecture — Implementation Plan
> **For Hermes + DeepSeek V4 Pro — execute session by session**
> **Memory is enabled — progress persists across sessions**

**Goal:** Deploy 10 language subdomains (en-us, pt-br, fr-ca, de-de, ru-ru, hi-in, ja-jp, zh-cn, ko-kr, ar-sa) while keeping coffeepie.co as Spanish (ES-CO). Wix/Avo code preserved — vanilla rewrite is Phase 2.

**Architecture:** Directory-per-locale with symlinked shared assets. Apache routes subdomain → locale directory. JS auto-detects locale from `window.location.hostname`.

---

## SESSION 1: Infrastructure — DNS, Apache, Directory Skeleton
**~3,000 tokens**

### Step 1: Create shared assets directory

Move Coffee Pie custom files to a central `shared/` directory that all locales symlink to:

```bash
mkdir -p /home/avolink/DEV/coffeepie/coffeepie_website/shared
cd /home/avolink/DEV/coffeepie/coffeepie_website/public

# Move Coffee Pie custom code to shared
mv js shared/js
mv css shared/css
mv images shared/images
mv assets shared/assets
mv translate.js shared/translate.js
mv translations.json shared/translations.json
mv header.js shared/header.js
mv header.css shared/header.css
mv footer.js shared/footer.js
mv footer.css shared/footer.css
mv manifest.json shared/manifest.json
mv favicon.svg shared/favicon.svg
```

### Step 2: Create locale directories with symlinks

```bash
LOCALES="en-us pt-br fr-ca de-de ru-ru hi-in ja-jp zh-cn ko-kr ar-sa"
BASE="/home/avolink/DEV/coffeepie/coffeepie_website"

for locale in $LOCALES; do
    mkdir -p "$BASE/$locale"
    cd "$BASE/$locale"
    
    # Symlink everything that's identical across locales
    ln -s ../public/productos .
    ln -s ../public/*_files .
    ln -s ../public/index_files .
    ln -s ../shared/js .
    ln -s ../shared/css .
    ln -s ../shared/images .
    ln -s ../shared/assets .
    ln -s ../shared/translate.js .
    ln -s ../shared/translations.json .
    ln -s ../shared/header.js .
    ln -s ../shared/header.css .
    ln -s ../shared/footer.js .
    ln -s ../shared/footer.css .
    ln -s ../shared/manifest.json .
    ln -s ../shared/favicon.svg .
    ln -s ../public/.htaccess .
    
    # Copy HTML files (these need per-locale modifications)
    cp ../public/*.html .
    cp ../public/404.html .
done
```

### Step 3: Modify shared JS for subdomain auto-detection

Edit `shared/translate.js` — add auto-detection, replace hardcoded DEFAULT_LOCALE:

```javascript
// REPLACE: var DEFAULT_LOCALE = 'ES-CO';
// WITH:
function getDefaultLocale() {
    var host = window.location.hostname;
    var map = {
        'en-us.coffeepie.co': 'EN-US',
        'es-co.coffeepie.co': 'ES-CO',
        'pt-br.coffeepie.co': 'PT-BR',
        'fr-ca.coffeepie.co': 'FR-CA',
        'de-de.coffeepie.co': 'DE-DE',
        'ru-ru.coffeepie.co': 'RU-RU',
        'hi-in.coffeepie.co': 'HI-IN',
        'ja-jp.coffeepie.co': 'JA-JP',
        'zh-cn.coffeepie.co': 'ZH-CN',
        'ko-kr.coffeepie.co': 'KO-KR',
        'ar-sa.coffeepie.co': 'AR-SA'
    };
    for (var key in map) {
        if (host === key) return map[key];
    }
    return 'ES-CO'; // coffeepie.co = Spanish
}
var DEFAULT_LOCALE = getDefaultLocale();
```

Edit `shared/js/lang.js` — same pattern:

```javascript
// REPLACE: var DEFAULT = 'es';
// WITH:
function getDefaultLang() {
    var host = window.location.hostname;
    var map = {
        'en-us.coffeepie.co': 'en', 'es-co.coffeepie.co': 'es',
        'pt-br.coffeepie.co': 'pt', 'fr-ca.coffeepie.co': 'fr',
        'de-de.coffeepie.co': 'de', 'ru-ru.coffeepie.co': 'ru',
        'hi-in.coffeepie.co': 'hi', 'ja-jp.coffeepie.co': 'ja',
        'zh-cn.coffeepie.co': 'zh', 'ko-kr.coffeepie.co': 'ko',
        'ar-sa.coffeepie.co': 'ar'
    };
    for (var key in map) { if (host === key) return map[key]; }
    return 'es';
}
var DEFAULT = getDefaultLang();
```

### Step 4: Per-locale HTML modifications

For EACH locale directory, run these `sed` replacements:

```bash
# For en-us:
cd /home/avolink/DEV/coffeepie/coffeepie_website/en-us
find . -name "*.html" -exec sed -i 's/<html lang="es"/<html lang="en-us"/g' {} +
find . -name "*.html" -exec sed -i 's/"userLanguage":"es"/"userLanguage":"en"/g' {} +

# For pt-br:
cd /home/avolink/DEV/coffeepie/coffeepie_website/pt-br
find . -name "*.html" -exec sed -i 's/<html lang="es"/<html lang="pt-br"/g' {} +
find . -name "*.html" -exec sed -i 's/"userLanguage":"es"/"userLanguage":"pt"/g' {} +
# ... repeat for each locale with its lang code
```

### Step 5: Apache VirtualHost configuration

Add to Apache config (or `.htaccess` at root with mod_rewrite):

```apache
# Detect locale from subdomain and route to correct directory
RewriteEngine On

# Extract locale from subdomain
RewriteCond %{HTTP_HOST} ^(en-us|pt-br|fr-ca|de-de|ru-ru|hi-in|ja-jp|zh-cn|ko-kr|ar-sa)\.coffeepie\.co$ [NC]
RewriteRule ^(.*)$ /home/avolink/DEV/coffeepie/coffeepie_website/%1/$1 [L]

# coffeepie.co (no subdomain) serves from public/ (Spanish)
RewriteCond %{HTTP_HOST} ^coffeepie\.co$ [NC]
RewriteRule ^(.*)$ /home/avolink/DEV/coffeepie/coffeepie_website/public/$1 [L]
```

### Verification

- Visit `en-us.coffeepie.co` → should show site with English language picker default
- Visit `coffeepie.co` → should show Spanish (unchanged)
- Check browser console: `DEFAULT_LOCALE` should match subdomain
- Check `<html lang>` attribute matches locale

---

## SESSION 2: SEO — Sitemaps & hreflang
**~2,000 tokens**

### Step 1: Generate per-locale sitemaps

Create a sitemap generator script that produces one sitemap per locale:

```bash
# For each locale, generate sitemap at /sitemap.xml
# Each URL in the sitemap includes hreflang alternates
```

Key rules:
- `en-us.coffeepie.co/sitemap.xml` → lists English URLs
- Each `<url>` block includes `<xhtml:link rel="alternate" hreflang="...">` for ALL other locales
- `x-default` points to `coffeepie.co` (Spanish root)

### Step 2: Add `<link rel="alternate">` to every HTML page

Add to `<head>` of every HTML file in every locale:

```html
<!-- Template for each page -->
<link rel="alternate" hreflang="es-co" href="https://coffeepie.co/PAGE" />
<link rel="alternate" hreflang="en-us" href="https://en-us.coffeepie.co/PAGE" />
<link rel="alternate" hreflang="pt-br" href="https://pt-br.coffeepie.co/PAGE" />
<!-- ... all 11 locales ... -->
<link rel="alternate" hreflang="x-default" href="https://coffeepie.co/PAGE" />
<link rel="canonical" href="https://SUBDOMAIN.coffeepie.co/PAGE" />
```

### Step 3: Root domain language redirect

Add to root `coffeepie.co` .htaccess:

```apache
# Detect browser language and redirect
RewriteCond %{HTTP:Accept-Language} ^es [NC]
RewriteRule ^$ https://coffeepie.co/ [L]  # Stay on Spanish

RewriteCond %{HTTP:Accept-Language} ^pt [NC]
RewriteRule ^$ https://pt-br.coffeepie.co/ [R=302,L]

RewriteCond %{HTTP:Accept-Language} ^en [NC]
RewriteRule ^$ https://en-us.coffeepie.co/ [R=302,L]

# Default: stay on Spanish root
```

---

## SESSION 3: DNS + SSL
**Manual step — Hermes cannot configure DNS**

For you (avolink) to do:
1. Add 10 CNAME records pointing each subdomain to coffeepie.co
2. If using Firebase Hosting: add 10 custom domains in Firebase Console
3. SSL: Firebase auto-provisions; for Apache, use Certbot with wildcard `*.coffeepie.co`

---

## SESSION 4: Cleanup — Remove Duplicated HTML from Public/
**~1,000 tokens**

Since `public/` is now just the Spanish root and symlinks, the HTML files at root should stay. But verify nothing is broken:

- `coffeepie.co/precios` → serves Spanish pricing
- `en-us.coffeepie.co/precios` → serves English pricing (still at /precios URL)
- Internal links work because they're relative (`./productos/...`)
- Coffee Pie JS loads because symlinks resolve correctly

---

## SESSION 5: Rolling Locale Deployment (Ongoing)

Not all 10 locales need perfect translations on day one. Deploy as translations mature:

1. **Week 1**: en-us (English — already well translated)
2. **Week 2**: pt-br (Portuguese — Brazil is key market)
3. **Week 3-4**: fr-ca, de-de (French, German)
4. **Month 2**: ja-jp, zh-cn, ko-kr (Asia)
5. **Month 3**: ru-ru, hi-in, ar-sa

Each new locale:
1. Run the directory creation + symlink script
2. Run the sed replacements
3. Add DNS CNAME
4. Update all existing sitemaps with new hreflang pair
5. Verify, then announce

---

## What This Costs (DeepSeek V4 Pro)

| Session | Est. tokens | Est. cost |
|---------|------------|-----------|
| Session 1: Infrastructure | ~15,000 | ~$0.05 |
| Session 2: SEO sitemaps | ~8,000 | ~$0.03 |
| Session 4: Cleanup | ~5,000 | ~$0.02 |
| Session 5: Per locale (×9 after en-us) | ~3,000 each | ~$0.01 each |
| **Total** | **~55,000** | **~$0.20** |

Plus the existing Wix/Avo code keeps working. No rewrite needed.

---

## What Does NOT Need to Change

- ❌ No Wix/Avo code modified or deleted
- ❌ No HTML pages rewritten — just `sed` on lang attributes
- ❌ No translations.json changes
- ❌ No Firebase/backend changes
- ❌ No frontend/Qt changes
- ❌ No security posture changes

## What DOES Need to Change

- ✅ 2 JS files: 20 lines added (subdomain auto-detection)
- ✅ HTML files: `sed` on `<html lang>` and `userLanguage` (per locale)
- ✅ Apache config: ~15 lines (subdomain routing)
- ✅ DNS: 10 CNAME records (manual)
- ✅ Sitemaps: generated per locale
