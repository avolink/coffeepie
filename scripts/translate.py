#!/usr/bin/env python3
"""
Coffee Pie - Batch Translate translations.json

Usage:
  1. Start LibreTranslate:  bash scripts/setup_translate.sh
  2. Run translations:      python3 scripts/translate.py
  3. Validate output:       python3 -m json.tool public/translations.json > /dev/null

Supports both backends:
  - LibreTranslate REST API  (default, needs Docker container on :5050)
  - Argos Translate offline  (set LIBRETRANSLATE_URL to empty string)

Environment variables:
  LIBRETRANSLATE_URL   API base URL (default: http://localhost:5050)
  BATCH_SIZE           Rows per batch (default: 20)
  SLEEP_MS             Delay between batches in ms (default: 300)
  TARGET_LANGS         Comma-separated list (default: pt,fr,de,ja,ko,zh,ru,ar,hi)
"""

import json, os, sys, time, urllib.request, urllib.error, re, pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Config ---
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(SCRIPTS_DIR, '..', 'coffeepie_website')
TRANSLATIONS_PATH = os.path.join(PROJECT_DIR, 'public', 'translations.json')
BACKUP_DIR = os.path.join(PROJECT_DIR, 'public', 'translations_backups')
API_URL = os.environ.get('LIBRETRANSLATE_URL', 'http://localhost:5050')
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '20'))
SLEEP_MS = float(os.environ.get('SLEEP_MS', '300'))
TARGET_LANGS = os.environ.get('TARGET_LANGS', 'pt,fr,de,ja,ko,zh,ru,ar,hi').split(',')
MAX_RETRIES = 3
MAX_WORKERS = 4

# Ensure backup directory exists
pathlib.Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)

# --- Utilities ---

def backup_original():
    ts = time.strftime('%Y%m%d_%H%M%S')
    dst = os.path.join(BACKUP_DIR, f'translations_{ts}.json')
    with open(TRANSLATIONS_PATH, 'r', encoding='utf-8') as src:
        original = src.read()
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(original)
    print(f'[backup] Saved to {dst}')
    return original

def load_translations():
    with open(TRANSLATIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_translations(data):
    tmp = TRANSLATIONS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, TRANSLATIONS_PATH)

def needs_translation(entry, lang):
    """Return True if this entry has Spanish but not the target language."""
    if not isinstance(entry, dict):
        return False
    if 'es' not in entry:
        return False
    if lang in entry and entry[lang] and entry[lang] != entry['es']:
        return False  # already translated
    return True

def collect_tasks(data):
    """Return dict: key -> list of (lang, spanish_text) needing translation."""
    tasks = {}
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        es_text = entry.get('es', '')
        if not es_text or len(es_text.strip()) < 2:
            continue
        # Check each target language
        for lang in TARGET_LANGS:
            if needs_translation(entry, lang):
                if key not in tasks:
                    tasks[key] = []
                tasks[key].append((lang, es_text))
    return tasks

# --- Translation backends ---

def translate_libretranslate(text, target_lang, source_lang='es'):
    """Call LibreTranslate REST API."""
    # LibreTranslate uses zh-Hans for Simplified Chinese (not zh)
    lt_lang = 'zh-Hans' if target_lang == 'zh' else target_lang
    url = f'{API_URL}/translate'
    payload = json.dumps({
        'q': text,
        'source': source_lang,
        'target': lt_lang,
        'format': 'text'
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json'
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('translatedText', '')
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'HTTP {e.code}: {body[:200]}') from e

def translate_argostranslate(text, target_lang, source_lang='es'):
    """Use local Argos Translate library (offline)."""
    import argostranslate.translate
    # Normalize to Argos codes (es, pt, fr, de, ja, ko, zh, ru, ar, hi)
    # Argos uses IETF BCP 47-ish codes
    result = argostranslate.translate.translate(text, source_lang, target_lang)
    return result

# Auto-detect which backend to use
USE_ARGOS = False
if not API_URL:
    try:
        import argostranslate.translate
        USE_ARGOS = True
        print('[mode] Using Argos Translate (offline)')
    except ImportError:
        print('[error] LIBRETRANSLATE_URL is empty and argostranslate not installed.')
        print('[error] Install with: pip install argostranslate')
        sys.exit(1)
else:
    print(f'[mode] Using LibreTranslate at {API_URL}')

def translate_one(text, target_lang, retries=MAX_RETRIES):
    """Translate with retry logic."""
    last_err = None
    for attempt in range(retries):
        try:
            if USE_ARGOS:
                return translate_argostranslate(text, target_lang)
            else:
                return translate_libretranslate(text, target_lang)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = (attempt + 1) * 2
                print(f'  [retry] {target_lang}: waiting {wait}s ({e})')
                time.sleep(wait)
    raise RuntimeError(f'Failed after {retries} retries: {last_err}')

# --- Batch processing ---

def check_api_health():
    """Verify the translation backend is reachable."""
    if USE_ARGOS:
        print('[health] Argos Translate (offline) - no health check needed')
        return True
    try:
        url = f'{API_URL}/languages'
        with urllib.request.urlopen(url, timeout=10) as resp:
            langs = json.loads(resp.read().decode('utf-8'))
            codes = {l['code'] for l in langs}
            required = set(TARGET_LANGS) | {'es'}
            if not required.issubset(codes):
                missing = required - codes
                print(f'[warn] LibreTranslate missing languages: {missing}')
                print(f'[warn] Available: {codes}')
            print(f'[health] LibreTranslate OK - {len(langs)} languages available')
            return True
    except Exception as e:
        print(f'[error] Cannot reach LibreTranslate at {API_URL}: {e}')
        print('[error] Run: bash scripts/setup_translate.sh  first')
        return False

def run_translation(all_tasks, data):
    """Process all translation tasks using thread pool."""
    total = sum(len(lang_tasks) for lang_tasks in all_tasks.values())
    done = 0
    errors = {}
    lock = __import__('threading').Lock()

    # Flatten tasks for parallel processing
    flat_tasks = []
    for key, lang_tasks in all_tasks.items():
        for lang, text in lang_tasks:
            flat_tasks.append((key, lang, text))

    print(f'\n[tasks] {total} translations across {len(flat_tasks)} entries')

    def worker(args):
        key, lang, text = args
        try:
            translated = translate_one(text, lang)
            return (key, lang, translated, None)
        except Exception as e:
            return (key, lang, None, str(e))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit in batches to avoid overwhelming the server
        for batch_start in range(0, len(flat_tasks), BATCH_SIZE):
            batch = flat_tasks[batch_start:batch_start + BATCH_SIZE]
            futures = [executor.submit(worker, t) for t in batch]

            batch_results = []
            for f in as_completed(futures):
                key, lang, translated, err = f.result()
                with lock:
                    if err:
                        errors[f'{key}|{lang}'] = err
                        print(f'  [FAIL] {key[:60]} -> {lang}: {err[:100]}')
                    else:
                        data[key][lang] = translated
                        done += 1
                        pct = done / total * 100
                        print(f'  [{done}/{total} {pct:.1f}%] {key[:60]} -> {lang}')

            # Save after each batch
            save_translations(data)
            if not USE_ARGOS:
                time.sleep(SLEEP_MS / 1000)

    # Report
    print(f'\n[summary]')
    print(f'  Translated: {done}/{total}')
    print(f'  Errors:     {len(errors)}')
    if errors:
        for k, v in list(errors.items())[:5]:
            print(f'    {k}: {v}')
    print(f'  Saved to:   {TRANSLATIONS_PATH}')

# --- Main ---

def main():
    # Health check
    if not check_api_health():
        sys.exit(1)

    # Backup
    backup_original()

    # Load
    data = load_translations()
    print(f'[load] {len(data)} entries loaded')

    # Collect tasks
    tasks = collect_tasks(data)
    if not tasks:
        print('[done] All entries already translated!')
        return

    entries_count = len(tasks)
    langs_count = sum(len(v) for v in tasks.values())
    print(f'[pending] {entries_count} entries, {langs_count} translations needed')

    # Run
    run_translation(tasks, data)

    # Final validation
    try:
        with open(TRANSLATIONS_PATH, 'r') as f:
            json.load(f)
        print('[validate] JSON is valid')
    except json.JSONDecodeError as e:
        print(f'[ERROR] translations.json is corrupted! Restore from backup: {e}')

if __name__ == '__main__':
    main()
