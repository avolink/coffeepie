#!/usr/bin/env python3
"""Translate all Spanish entries to English using LibreTranslate on localhost:5050."""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = os.environ.get('LIBRETRANSLATE_URL', 'http://localhost:5050')
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATIONS_PATH = os.path.join(SCRIPTS_DIR, '..', 'coffeepie_website', 'public', 'translations.json')
BATCH_SIZE = 30
MAX_RETRIES = 3
MAX_WORKERS = 4
SLEEP_MS = 200

def load_translations():
    with open(TRANSLATIONS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_translations(data):
    tmp = TRANSLATIONS_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp, TRANSLATIONS_PATH)

def translate_one(text, retries=MAX_RETRIES):
    url = f'{API_URL}/translate'
    payload = json.dumps({
        'q': text,
        'source': 'es',
        'target': 'en',
        'format': 'text'
    }).encode('utf-8')
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('translatedText', '')
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep((attempt + 1) * 2)
    raise RuntimeError(f'Failed after {retries} retries: {last_err}')

def main():
    # Health check
    try:
        with urllib.request.urlopen(f'{API_URL}/languages', timeout=10) as resp:
            print(f'[health] LibreTranslate OK at {API_URL}')
    except Exception as e:
        print(f'[error] Cannot reach LibreTranslate: {e}')
        sys.exit(1)

    data = load_translations()
    print(f'[load] {len(data)} entries')

    # Collect entries needing English translation
    tasks = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        es_text = entry.get('es', '')
        if not es_text or len(es_text.strip()) < 2:
            continue
        # Skip if already has non-identical English translation
        if 'en' in entry and entry['en'] and entry['en'] != es_text:
            continue
        tasks.append((key, es_text))

    if not tasks:
        print('[done] All entries already have English translations!')
        return

    total = len(tasks)
    print(f'[pending] {total} translations needed')

    done = 0
    errors = {}
    lock = __import__('threading').Lock()

    def worker(args):
        key, text = args
        try:
            translated = translate_one(text)
            return (key, translated, None)
        except Exception as e:
            return (key, None, str(e))

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_start in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[batch_start:batch_start + BATCH_SIZE]
            futures = [executor.submit(worker, t) for t in batch]

            for f in as_completed(futures):
                key, translated, err = f.result()
                with lock:
                    if err:
                        errors[key] = err
                        sys.stderr.write(f'  [FAIL] {key[:60]}: {err[:100]}\n')
                    else:
                        data[key]['en'] = translated
                        done += 1
                        pct = done / total * 100
                        if done % 20 == 0 or done == total:
                            sys.stderr.write(f'  [{done}/{total} {pct:.1f}%]\n')

            save_translations(data)
            time.sleep(SLEEP_MS / 1000)

    print(f'\n[summary] Translated: {done}/{total}')
    print(f'[summary] Errors: {len(errors)}')
    if errors:
        for k in list(errors.keys())[:5]:
            print(f'  {k}: {errors[k]}')
    print(f'[saved] {TRANSLATIONS_PATH}')

if __name__ == '__main__':
    main()
