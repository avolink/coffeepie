# Coffee Pie - Translation Management Guide

## Canonical TMS: Weblate

Weblate is the canonical Translation Management System for Coffee Pie. It provides a web-based GUI that allows translators (technical and non-technical) to contribute without touching code or JSON directly. Weblate syncs bidirectionally with this GitHub repository — translations approved in Weblate are committed as pull requests automatically.

**Why Weblate over manual JSON editing:**
- No syntax errors (Weblate validates JSON on save)
- No merge conflicts from concurrent translators
- Glossary enforcement prevents mistranslation of brand terms
- Machine translation pre-fill with mandatory human review (voting)
- Non-technical translators don't need to know Git or JSON

### Setup Options

#### Option A: Hosted Weblate (free for public repos)
1. Go to https://hosted.weblate.org
2. Sign in with your GitHub account
3. Add this repository (`avolink/coffeepie`) as a new translation project
4. Point it at the translation files under `coffeepie_website/public/locales/`
5. Configure: source language = Spanish (`es`), file format = JSON with nested structure
6. Done — translators get a web UI immediately

#### Option B: Self-Hosted (Docker)
Create `weblate/docker-compose.yml`:

```yaml
version: '3'
services:
  weblate:
    image: weblate/weblate
    ports:
      - "8080:80"
    environment:
      WEBLATE_SITE_DOMAIN: "translate.coffeepie.co"
      WEBLATE_ADMIN_EMAIL: "admin@coffeepie.co"
      WEBLATE_ADMIN_PASSWORD: "${WEBLATE_ADMIN_PASSWORD}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
      REDIS_PASSWORD: "${REDIS_PASSWORD}"
    volumes:
      - weblate_data:/app/data
    restart: always

  database:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
      POSTGRES_USER: weblate
      POSTGRES_DB: weblate
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  cache:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redis_data:/data
    restart: always

volumes:
  weblate_data:
  postgres_data:
  redis_data:
```

Start with:
```bash
cd weblate
echo "WEBLATE_ADMIN_PASSWORD=changeme" > .env
echo "POSTGRES_PASSWORD=changeme" >> .env
echo "REDIS_PASSWORD=changeme" >> .env
docker compose up -d
```

Then configure Weblate's admin UI to connect to `https://github.com/avolink/coffeepie.git` using a bot account's Personal Access Token.

---

## Translation File Structure

### Current: Monolithic JSON
```
coffeepie_website/public/translations.json   (1.88 MB, 1,289 entries, 11 languages)
```

Keys are Spanish source text, values are objects with language codes:
```json
{
  "PRECIOS": {
    "en": "PRICES",
    "es": "PRECIOS",
    "pt": "PREÇOS"
  }
}
```

### Target: Namespaced JSON (for Weblate compatibility)
```
coffeepie_website/public/locales/
  es/
    common.json      ← navigation, labels, short text
    pages.json       ← page content, sections, long paragraphs
    products.json    ← product descriptions, specs, store
    legal.json       ← privacy policy, terms of service
    faq.json         ← Q&A entries
    brand.json       ← brand terms (should be identical across all languages)
  en/
    common.json
    ...
  pt/  fr/  de/  ja/  ko/  zh/  ru/  ar/  hi/
```

Each file uses ICU MessageFormat for complex plurals, genders, and variables:
```json
{
  "slices.count": "{count, plural, =0 {No slices} one {# slice} other {# slices}}",
  "credits.remaining": "{credits, number} credits remaining",
  "date.expires": "Expires {date, date, long}"
}
```

### Migration (from monolithic to namespaced)

Run `scripts/migrate_to_namespaces.py` (to be created) which:
1. Reads `translations.json`
2. Classifies each entry into a namespace based on content patterns
3. Generates short semantic keys (e.g., `pages.hero.modularidad`)
4. Writes one file per language per namespace
5. Generates `key_map.json` for backward compatibility

---

## Translation Policies

### Language-Independent Identifiers (DO NOT TRANSLATE)

The following must remain **identical** across all 11 languages in any translation file:

| Category | Examples |
|---|---|
| Email addresses | `accesibilidad.coffeepie@grupo3p1.co` |
| Physical addresses | `Cr 46 #56-11, La Candelaria, Medellín, Antioquia.` |
| Brand names with registered trademarks | `Coffee Pie®`, `Commanders™`, `Sentinels™`, `Rangers™` |
| Company/project names | `QFDM`, `OpenUDS`, `Sunshine`, `Moonlight`, `Proxmox` |
| URLs and API endpoints | `https://api.coffeepie.co`, `www.coffeepie.co` |
| Technical specs and units | `1 Wh`, `8 GB`, `1 Core`, `3 TOPS`, `15 vMPX/s` |
| Social media handles | `Instagram`, `Facebook`, `TikTok`, `Youtube` |
| Trademark/Copyright symbols | `™`, `®`, `©` — never replace with plain text `TM`, `(R)`, `(C)` |

These identifiers should store the **same value** for all language codes (`en`, `es`, `pt`, `fr`, `de`, `ru`, `hi`, `ja`, `zh`, `ko`, `ar`).

### Automated Translation Tools

**Never** run automated translation tools (LibreTranslate, Google Translate API, etc.) on the entire `translations.json` file. Automated translation tools:
- Mistranslate proper nouns (e.g., `INICIO` became `INITIO` instead of `HOME`)
- Corrupt HTML/special characters (e.g., `|||` paragraph separators became `h.124;` fragments)
- Produce misleading output in non-Latin scripts (e.g., Japanese `ホーム` became `インティオ`, Chinese `首页` became `印度`)

**Instead**, use Weblate which supports machine translation pre-fill **with mandatory human review**, glossary enforcement, and voting workflows.

All LibreTranslate/AI batch-translation scripts have been deleted. Weblate is the only supported translation workflow for production.

### Translation Workflow

1. **Source language:** Spanish (`es`) — the canonical, correct version
2. **Machine pre-fill:** Weblate can use DeepL, Google Translate, or an LLM API to generate draft translations for new keys. These drafts are marked as "Needs review."
3. **Human review:** At least one reviewer must approve each machine-generated translation before it is merged
4. **Glossary enforcement:** Weblate warns translators when a term has a canonical translation defined in the glossary
5. **Voting:** Community members can upvote/downvote translations. A minimum vote threshold can be configured
6. **CI validation:** GitHub Actions validate JSON syntax, key consistency, and no empty translations on every PR (see `.github/workflows/validate-translations.yml`)

---

## Glossary of Canonical Translations

| Spanish (source) | English | Portuguese | Notes |
|---|---|---|---|
| Terminales Codec | Codec Terminals | Terminais Codec | NOT "Codec terminals" (inconsistent caps) |
| Terminales Codec Modulares | Modular Codec Terminals | Terminais Codec Modulares | |
| Commanders™ | Commanders™ | Commanders™ | ™ is Unicode, not plain TM |
| Sentinels™ | Sentinels™ | Sentinels™ | |
| Rangers™ | Rangers™ | Rangers™ | |
| Coffee Pie® | Coffee Pie® | Coffee Pie® | ® is Unicode, not plain (R) |
| QFDM | QFDM | QFDM | Do not translate acronym |
| Sostenibilidad | Sustainability | Sustentabilidade | |
| Modularidad | Modularity | Modularidade | |
| Precios | Prices | Preços | |
| Tienda | Store | Loja | |
| Inicio | Home | Início | NOT "INITIO" (machine translation error) |
| Acerca de | About | Sobre | |
| Panel de Usuario | User Panel | Painel do Usuário | NOT "BAN OF USER" (machine translation error) |
| Anunciantes | Advertisers | Anunciantes | NOT "Announcers" |
| Fabricantes | Manufacturers | Fabricantes | |
| Consumidores Directos | Direct Consumers | Consumidores Diretos | |
| Proveedor de Internet (ISP) | Internet Service Provider (ISP) | Provedor de Internet (ISP) | |

---

## GitHub Actions CI/CD

Create `.github/workflows/validate-translations.yml`:

```yaml
name: Validate Translations
on:
  pull_request:
    paths:
      - 'coffeepie_website/public/locales/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Validate JSON syntax
        run: |
          for f in coffeepie_website/public/locales/*/*.json; do
            node -e "JSON.parse(require('fs').readFileSync('$f','utf8'))" || exit 1
          done

      - name: Check all languages have same keys
        run: |
          node -e "
          const fs = require('fs');
          const dirs = fs.readdirSync('coffeepie_website/public/locales');
          const keysets = {};
          let errors = 0;
          dirs.forEach(lang => {
            const files = fs.readdirSync('coffeepie_website/public/locales/' + lang);
            files.forEach(f => {
              const data = JSON.parse(fs.readFileSync('coffeepie_website/public/locales/' + lang + '/' + f, 'utf8'));
              keysets[f] = keysets[f] || [];
              keysets[f].push({lang, keys: Object.keys(data).sort()});
            });
          });
          for (const [ns, entries] of Object.entries(keysets)) {
            const refKeys = entries[0].keys.join(',');
            entries.forEach(e => {
              if (e.keys.join(',') !== refKeys) {
                const missing = entries[0].keys.filter(k => !e.keys.includes(k));
                const extra = e.keys.filter(k => !entries[0].keys.includes(k));
                if (missing.length) console.error('MISSING KEYS in', ns, e.lang + ':', missing.join(', '));
                if (extra.length) console.error('EXTRA KEYS in', ns, e.lang + ':', extra.join(', '));
                errors++;
              }
            });
          }
          process.exit(errors > 0 ? 1 : 0);
          "

      - name: Check no empty translations
        run: |
          node -e "
          const fs = require('fs');
          const dirs = fs.readdirSync('coffeepie_website/public/locales');
          let errors = 0;
          dirs.forEach(lang => {
            const files = fs.readdirSync('coffeepie_website/public/locales/' + lang);
            files.forEach(f => {
              const data = JSON.parse(fs.readFileSync('coffeepie_website/public/locales/' + lang + '/' + f, 'utf8'));
              Object.entries(data).forEach(([k,v]) => {
                if (!v || v.trim() === '') { console.error('EMPTY:', lang, f, k); errors++; }
              });
            });
          });
          process.exit(errors > 0 ? 1 : 0);
          "
```

---

## Languages

| Code | Language | Script | Status |
|---|---|---|---|
| `es` | Spanish | Latin | Canonical source |
| `en` | English | Latin | Needs review |
| `pt` | Portuguese | Latin | Needs review |
| `fr` | French | Latin | Needs review |
| `de` | German | Latin | Needs review |
| `ru` | Russian | Cyrillic | Needs review |
| `hi` | Hindi | Devanagari | Needs review |
| `ja` | Japanese | Hiragana/Katakana/Kanji | Needs review |
| `zh` | Chinese (Simplified) | Hanzi | Needs review |
| `ko` | Korean | Hangul | Needs review |
| `ar` | Arabic | Arabic | Needs review |

**Note:** For non-Latin script languages (ru, hi, ja, zh, ko, ar), translations must contain characters from their native script. Latin-only text in these columns indicates an untranslated or machine-translated entry that needs human review.

---

## Quick Reference

| Task | Command / Action |
|---|---|
| Translate a string | Open Weblate at `translate.coffeepie.co`, find the key, enter translation |
| Add a new key | Add it to `locales/es/<namespace>.json`, then `git push` — Weblate auto-detects it |
| Review machine translations | Weblate shows "Needs review" badge — click Approve or Edit |
| Validate translations | PRs auto-validate via GitHub Actions |
| Check translation coverage | See `/TRANSLATIONS_AUDIT_REPORT.md` (generated periodically) |
