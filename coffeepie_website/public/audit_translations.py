#!/usr/bin/env python3
"""
Coffee Pie Translation Audit Script
====================================
Audits mismatches between Spanish text in HTML pages and Spanish keys in
translations.json, following the exact same normalization and extraction
logic as lang.js.

Reports:
  (A) HTML text with NO match in translations.json (missing keys)
  (B) translations.json keys NOT found in HTML (orphaned entries)
  (C) Near-misses where HTML text is similar but not identical to a key
"""

import json
import re
import os
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PUBLIC_DIR = Path(__file__).resolve().parent
TRANSLATIONS_FILE = PUBLIC_DIR / "translations.json"

# Main HTML pages (in public/ root, not in assets/, *_files/, productos/,
# css/, js/ directories)
MAIN_HTML_FILES = sorted(
    f for f in PUBLIC_DIR.glob("*.html")
    if not f.name.startswith(".")
)

# Tags/elements excluded by lang.js translateElement()  (top-level check)
EXCLUDED_TAGS = {"script", "style", "noscript", "code", "pre", "input", "textarea"}

# lang.js rules for skipping text nodes
MIN_TEXT_LENGTH = 2
NUMERIC_ONLY_RE = re.compile(r"^[\d\s.,'%$€£¥+#*\-–—]+$")

# Group separator used in translations.json for rich text components
GROUP_SEPARATOR = " ||| "

# Near-miss threshold
NEAR_MISS_MAX_DIST = 3
NEAR_MISS_MAX_RATIO = 0.15


# ---------------------------------------------------------------------------
# Normalization  (exact match of lang.js normalizeText)
# ---------------------------------------------------------------------------
def normalize_text(t):
    """Mirrors lang.js normalizeText()."""
    if not t:
        return ""
    t = re.sub(r"[\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Levenshtein distance  (for near-miss detection)
# ---------------------------------------------------------------------------
def levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1)
            ))
        prev = curr
    return prev[-1]


def is_near_miss(a, b):
    dist = levenshtein(a, b)
    max_len = max(len(a), len(b))
    if max_len == 0:
        return False
    ratio = dist / max_len
    return dist <= NEAR_MISS_MAX_DIST or ratio <= NEAR_MISS_MAX_RATIO


# ---------------------------------------------------------------------------
# Safe source-line access (Script objects lack sourceline)
# ---------------------------------------------------------------------------
def safe_line(obj, default=0):
    return int(getattr(obj, 'sourceline', default) or default)


# ---------------------------------------------------------------------------
# Text extraction from HTML  (mirrors lang.js translateElement)
# ---------------------------------------------------------------------------
def extract_translatable_texts(soup):
    """
    Walk the BeautifulSoup tree exactly as lang.js translateElement does,
    returning a dict: {normalized_text: [(file, tag, raw_text), ...]}
    """
    texts = {}  # normalized -> list of (line, element_tag, raw_original)

    def walk(el):
        if isinstance(el, NavigableString):
            return
        if not isinstance(el, Tag):
            return
        tag_name = el.name.lower() if el.name else ""

        # Top-level exclusion check (mirrors translateElement)
        if el.get("data-cp-no-translate") is not None:
            return
        if tag_name in EXCLUDED_TAGS:
            return

        # ---- Group-level translation for richTextElement ----
        if el.get("data-testid") == "richTextElement":
            text_parts = []
            for child in el.children:
                if not isinstance(child, Tag) and not (isinstance(child, NavigableString) and child.strip()):
                    continue
                text = (child.get_text(strip=False) or "").strip()
                if len(text) < 2:
                    continue
                if re.match(r"^[\s\u200B\u00A0]*$", text):
                    continue
                text_parts.append(text)

            if len(text_parts) >= 2:
                concat = GROUP_SEPARATOR.join(text_parts)
                norm = normalize_text(concat)
                if norm and len(norm) >= MIN_TEXT_LENGTH:
                    texts.setdefault(norm, []).append(
                        (safe_line(el), el.name, concat)
                    )

        # ---- Process child nodes (mirrors translateElement) ----
        children = list(el.children)
        for node in children:
            if isinstance(node, NavigableString):
                # Direct text node child
                text = str(node)
                norm = normalize_text(text)
                if norm and len(norm) >= MIN_TEXT_LENGTH and not NUMERIC_ONLY_RE.match(norm):
                    texts.setdefault(norm, []).append(
                        (safe_line(node), tag_name, text)
                    )

            elif isinstance(node, Tag):
                child_tag = node.name.lower() if node.name else ""

                # Check excluded tags for the child too (lang.js always
                # re-enters translateElement which has the exclusion check)
                if child_tag in EXCLUDED_TAGS:
                    continue
                if node.get("data-cp-no-translate") is not None:
                    continue

                node_children = list(node.children)
                tag_children = [c for c in node_children if isinstance(c, Tag)]

                # Leaf element: no tag children + exactly 1 non-whitespace
                # text child  (matches lang.js: children.length===0 &&
                # childNodes.length===1 && firstChild.nodeType===TEXT_NODE)
                non_empty_text = [
                    c for c in node_children
                    if isinstance(c, NavigableString) and str(c).strip()
                ]
                if len(tag_children) == 0 and len(non_empty_text) == 1:
                    text = str(non_empty_text[0])
                    norm = normalize_text(text)
                    if norm and len(norm) >= MIN_TEXT_LENGTH and not NUMERIC_ONLY_RE.match(norm):
                        texts.setdefault(norm, []).append(
                            (safe_line(non_empty_text[0]), child_tag, text)
                        )
                else:
                    # Recurse into non-leaf element nodes
                    walk(node)

    body = soup.body or soup
    walk(body)
    return texts


def parse_html_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return BeautifulSoup(content, "html.parser")


# ---------------------------------------------------------------------------
# Load translations.json
# ---------------------------------------------------------------------------
def load_translations():
    with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    es_keys = {}     # normalized -> [raw key strings]
    es_keys_raw = set()

    for key, entry in data.items():
        es_val = entry.get("es", "")
        es_keys_raw.add(es_val)
        norm = normalize_text(es_val)
        if norm:
            es_keys.setdefault(norm, []).append(key)

    return es_keys, es_keys_raw, data


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------
def run_audit():
    print("=" * 78)
    print("Coffee Pie Translation Audit")
    print("=" * 78)
    print()

    # Load translations
    print(f"Loading translations.json ({TRANSLATIONS_FILE.stat().st_size:,} bytes)...")
    trans_norm, trans_raw, trans_data = load_translations()
    print(f"  {len(trans_raw):,} total Spanish keys")
    print(f"  {len(trans_norm):,} unique normalized keys")
    print()

    # Extract text from HTML files
    print(f"Extracting text from {len(MAIN_HTML_FILES)} HTML files...")
    html_texts = {}  # normalized -> [(filename, line, tag, raw), ...]
    file_stats = []

    for html_file in MAIN_HTML_FILES:
        try:
            soup = parse_html_file(html_file)
            file_texts = extract_translatable_texts(soup)
            count = 0
            for norm, entries in file_texts.items():
                count += len(entries)
                for (line, tag, raw) in entries:
                    html_texts.setdefault(norm, []).append(
                        (html_file.name, line, tag, raw)
                    )
            file_stats.append((html_file.name, len(file_texts), count))
        except Exception as e:
            print(f"  ERROR parsing {html_file.name}: {e}", file=sys.stderr)

    print(f"  {len(html_texts):,} unique normalized text strings across all pages")
    print()

    # Per-file breakdown
    print("  --- Per-file breakdown ---")
    for fname, unique, total in file_stats:
        print(f"    {fname:<42s} {unique:>5,} unique / {total:>6,} total")
    print()

    # -----------------------------------------------------------------------
    # Report A: HTML text with NO match in translations.json
    # -----------------------------------------------------------------------
    html_norm_set = set(html_texts.keys())
    trans_norm_set = set(trans_norm.keys())

    missing_from_translations = html_norm_set - trans_norm_set
    print("=" * 78)
    print(f"REPORT A: HTML text MISSING from translations.json ({len(missing_from_translations)} items)")
    print("=" * 78)
    print()

    if missing_from_translations:
        sorted_missing = sorted(missing_from_translations, key=lambda x: (len(x), x))
        for i, norm in enumerate(sorted_missing):
            entries = html_texts[norm]
            files = sorted(set(e[0] for e in entries))
            raw = entries[0][3]
            files_str = ', '.join(files[:3])
            if len(files) > 3:
                files_str += f'... (+{len(files) - 3})'
            print(f"  #{i+1:04d}  [{files_str}]")
            print(f"         Text: {repr(raw[:140])}{'...' if len(raw) > 140 else ''}")
            print()
    else:
        print("  None found! All HTML text has a translations.json entry.")
        print()

    # -----------------------------------------------------------------------
    # Report B: translations.json keys NOT in any HTML file
    # -----------------------------------------------------------------------
    orphaned = trans_norm_set - html_norm_set
    print("=" * 78)
    print(f"REPORT B: translations.json entries NOT in HTML ({len(orphaned)} orphaned)")
    print("=" * 78)
    print()

    if orphaned:
        sorted_orphaned = sorted(orphaned, key=lambda x: (len(x), x))
        for i, norm in enumerate(sorted_orphaned):
            keys = trans_norm[norm]
            rt = trans_data[keys[0]].get("es", "")
            en_val = trans_data[keys[0]].get("en", "")
            print(f"  #{i+1:04d}  Key(s): {keys[:2]}{'...' if len(keys) > 2 else ''}")
            print(f"         ES: {repr(rt[:140])}{'...' if len(rt) > 140 else ''}")
            if en_val and en_val != rt:
                print(f"         EN: {repr(en_val[:140])}{'...' if len(en_val) > 140 else ''}")
            print()
    else:
        print("  None found! All translations.json entries appear in HTML.")
        print()

    # -----------------------------------------------------------------------
    # Report C: Near-misses  (HTML text similar to but not identical to key)
    # -----------------------------------------------------------------------
    print("=" * 78)
    print("REPORT C: Near-misses (HTML text SIMILAR to translations.json key)")
    print("=" * 78)
    print(f"  Threshold: distance <= {NEAR_MISS_MAX_DIST} OR ratio <= {NEAR_MISS_MAX_RATIO}")
    print()

    near_misses = []
    trans_norm_list = sorted(trans_norm_set)

    for html_norm in sorted(missing_from_translations):
        best = None
        best_dist = float('inf')
        for trans_n in trans_norm_list:
            # Quick length filter: skip pairs with >50% length difference
            max_len = max(len(html_norm), len(trans_n))
            if abs(len(html_norm) - len(trans_n)) > max_len * 0.6:
                # Only do full check if length difference isn't too extreme
                if abs(len(html_norm) - len(trans_n)) > NEAR_MISS_MAX_DIST * 4:
                    continue
            if is_near_miss(html_norm, trans_n):
                dist = levenshtein(html_norm, trans_n)
                if dist < best_dist:
                    best_dist = dist
                    best = trans_n
        if best is not None:
            near_misses.append((html_norm, best, best_dist))

    if near_misses:
        near_misses.sort(key=lambda x: x[2])
        shown = 0
        for html_norm, trans_n, dist in near_misses:
            if shown >= 50:
                print(f"  ... and {len(near_misses) - 50} more near-misses "
                      f"(see audit_report.txt for full list)")
                break
            entries = html_texts[html_norm]
            files = sorted(set(e[0] for e in entries))
            files_str = ', '.join(files[:3])
            if len(files) > 3:
                files_str += f'... (+{len(files) - 3})'
            keys = trans_norm[trans_n]
            print(f"  #{shown+1:04d}  [{files_str}]")
            print(f"         Dist: {dist} | Key: {keys[0]}")
            print(f"         HTML: {repr(html_norm[:130])}{'...' if len(html_norm) > 130 else ''}")
            print(f"         JSON: {repr(trans_n[:130])}{'...' if len(trans_n) > 130 else ''}")
            print()
            shown += 1
        print(f"  Total near-misses: {len(near_misses)}")
    else:
        print("  No near-misses found.")
    print()

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"  Total translations.json keys (raw):     {len(trans_raw):>7,}")
    print(f"  Total translations.json keys (norm):    {len(trans_norm):>7,}")
    print(f"  Total unique HTML texts:                {len(html_texts):>7,}")
    print(f"  HTML texts MISSING from translations:   {len(missing_from_translations):>7,}")
    print(f"  translations.json entries NOT in HTML:  {len(orphaned):>7,}")
    print(f"  Near-misses detected:                   {len(near_misses):>7,}")
    print()

    # -----------------------------------------------------------------------
    # Write detailed report file
    # -----------------------------------------------------------------------
    report_path = PUBLIC_DIR / "audit_report.txt"
    with open(report_path, "w", encoding="utf-8") as rf:
        rf.write("Coffee Pie Translation Audit Report\n")
        rf.write("=" * 78 + "\n\n")

        rf.write(f"Files audited: {len(MAIN_HTML_FILES)}\n")
        for f in MAIN_HTML_FILES:
            rf.write(f"  {f.name}\n")
        rf.write("\n")

        rf.write(f"Per-file counts:\n")
        for fname, unique, total in file_stats:
            rf.write(f"  {fname:<42s} {unique:>5,} unique / {total:>6,} total\n")
        rf.write("\n")

        rf.write(f"\n{'='*78}\n")
        rf.write(f"REPORT A: HTML text MISSING from translations.json ({len(missing_from_translations)})\n")
        rf.write(f"{'='*78}\n")
        for norm in sorted(missing_from_translations, key=lambda x: (len(x), x)):
            entries = html_texts[norm]
            files_set = sorted(set(e[0] for e in entries))
            rf.write(f"  Norm: {repr(norm)}\n")
            rf.write(f"  Raw:  {repr(entries[0][3])}\n")
            rf.write(f"  Files: {', '.join(files_set)}\n")
            rf.write("\n")

        rf.write(f"\n{'='*78}\n")
        rf.write(f"REPORT B: translations.json entries NOT in HTML ({len(orphaned)})\n")
        rf.write(f"{'='*78}\n")
        for norm in sorted(orphaned, key=lambda x: (len(x), x)):
            for key in trans_norm.get(norm, []):
                entry = trans_data.get(key, {})
                rf.write(f"  Key: {repr(key)}\n")
                rf.write(f"  ES:  {repr(entry.get('es', ''))}\n")
                en_val = entry.get('en', '')
                if en_val and en_val != entry.get('es', ''):
                    rf.write(f"  EN:  {repr(en_val)}\n")
                rf.write("\n")

        rf.write(f"\n{'='*78}\n")
        rf.write(f"REPORT C: Near-misses ({len(near_misses)})\n")
        rf.write(f"{'='*78}\n")
        for html_norm, trans_n, dist in near_misses:
            rf.write(f"  HTML: {repr(html_norm)}\n")
            rf.write(f"  JSON: {repr(trans_n)}\n")
            rf.write(f"  Distance: {dist}\n")
            rf.write(f"  JSON Key: {trans_norm[trans_n][0]}\n")
            rf.write(f"  HTML files: {', '.join(sorted(set(e[0] for e in html_texts[html_norm])))}\n")
            rf.write("\n")

    print(f"Detailed report written to: {report_path}")
    print()
    print("=" * 78)
    print("PREVENTION RECOMMENDATIONS")
    print("=" * 78)
    print()
    print("1. Add this audit script as a pre-commit hook so every commit that")
    print("   touches HTML or translations.json runs the audit automatically.")
    print()
    print("2. Treat translations.json keys as the SOURCE OF TRUTH. When fixing")
    print("   a typo: update BOTH the HTML text AND the corresponding key in")
    print("   translations.json simultaneously.")
    print()
    print("3. Or: after fixing a typo in HTML, run this script to find the")
    print("   near-missed translation key and update its Spanish value.")
    print()
    print("4. Use the 'data-cp-no-translate' attribute on elements that should")
    print("   NEVER be translated (like brand names, email addresses).")
    print()
    print("5. For group translations (richTextElement components), ensure the")
    print("   text in child elements exactly matches what is in the JSON keys")
    print(f"   when joined with '{GROUP_SEPARATOR}'.")
    print()
    print("6. Run this script on every CI build and fail if new mismatches are")
    print("   introduced (treat it as a lint check).")


if __name__ == "__main__":
    run_audit()
