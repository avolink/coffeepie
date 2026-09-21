#!/usr/bin/env python3
"""
check-doc-consistency.py — Policy coherence checker for Coffee Pie documentation.

Verifies that key policy values are identical across all core documentation files.
Run in CI or locally: python scripts/check-doc-consistency.py

Exit: 0 = all consistent, 1 = drift detected.
"""

import re
import sys
from pathlib import Path

# The report uses Unicode marks (✓). On Windows the default console encoding
# is cp1252, which cannot encode them and crashes the script. Force UTF-8 so
# contributors can run this locally on any platform, matching CI (Linux).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent

# ── Checks ────────────────────────────────────────────────────────────
# Each check: (description, {file_path: required_pattern, ...})

CHECKS = [
    # ── Wallet holding limit ──
    (
        "Wallet holding limit: 100'000'000'000 COFP per wallet (or 10% of total supply)",
        {
            "AGENTS.md": r"100'000'000'000 COFP per wallet.*(?:or )?10% of the total supply",
            "README.md": r"100'000'000'000 COFP per wallet.*(?:or )?10% of the total supply",
            "CONSTITUTION.md": r"100'000'000'000 COFP.*(?:or )?10% of the total supply",
            "blockchain/README.md": r"100,000,000,000 COFP per wallet.*(?:or )?10% of the total supply",
        },
    ),
    # ── Initial supply ──
    (
        "Initial supply: 100'000'000 COFP (elastic, no cap)",
        {
            "AGENTS.md": r"initial supply of 100'000'000 COFP",
            "README.md": r"initial supply of 100'000'000 COFP",
            "blockchain/COFP_Token.sol": r"INITIAL_SUPPLY = 100_000_000",
            "blockchain/DEPLOY.md": r"Initial Supply.*100'?000'?000 COFP",
        },
    ),
    # ── No MAX_SUPPLY / no fixed supply ──
    (
        "No MAX_SUPPLY constant (elastic supply, no cap)",
        {
            "blockchain/COFP_Token.sol": r"^((?!MAX_SUPPLY).)*$",
            "AGENTS.md": r"^((?!fixed.supply).)*$",
            "README.md": r"^((?!fixed.supply).)*$",
            "blockchain/DEPLOY.md": r"^((?!MAX_SUPPLY).)*$",
            "CONSTITUTION.md": r"^((?!100'000'000/100'000'000).)*$",
        },
    ),
    # ── Elastic supply / no cap ──
    (
        "Elastic supply model (no cap) stated",
        {
            "AGENTS.md": r"[Ee]lastic supply",
            "README.md": r"[Ee]lastic supply",
            "blockchain/DEPLOY.md": r"[Ee]lastic.?supply",
        },
    ),
    # ── COFP unit: 1 COFP = 1 Slice·min ──
    (
        "COFP unit: 1 COFP = 1 Slice per minute",
        {
            "AGENTS.md": r"1 COFP = 1.*Slice.*(?:for|served|per).*(?:1 )?minute",
            "README.md": r"1 COFP = 1.*Slice.*(?:for|served|per).*(?:1 )?minute",
            "blockchain/README.md": r"1 COFP = 1.*Slice.*(?:for|served|per).*(?:1 )?minute",
            "blockchain/DEPLOY.md": r"1 COFP.*per Slice.*min",
        },
    ),
    # ── Contributors cannot burn for fiat ──
    (
        "Contributors cannot burn COFP for fiat",
        {
            "AGENTS.md": r"Contributors cannot burn COFP for fiat",
            "README.md": r"Contributors cannot burn COFP for fiat",
            "CONSTITUTION.md": r"Contributors cannot burn COFP for fiat",
            "blockchain/README.md": r"Cannot burn COFP for fiat",
        },
    ),
    # ── Trusted Providers (not just "Providers") for fiat burning ──
    (
        "Trusted Providers for fiat burning",
        {
            "CONSTITUTION.md": r"Trusted Providers.*burn.*fiat",
            "AGENTS.md": r"Trusted Providers.*burn.*fiat",
            "README.md": r"Trusted Providers.*burn.*fiat",
        },
    ),
    # ── Backend-enforced limits ──
    (
        "Wallet limits backend-enforced, not on-chain",
        {
            "CONSTITUTION.md": r"enforced by the Coffee.?Pie.? backend",
            "AGENTS.md": r"enforced by the Coffee Pie.*backend",
            "README.md": r"enforced by the Coffee Pie.*backend",
        },
    ),
    # ── Conversion: Consumer 20 Cr/COP + Contributor 10 Cr/COFP burn ──
    (
        "Contributor burn rate: 10 Cr per COFP",
        {
            "AGENTS.md": r"burn COFP.*Credits.*10 Cr per COFP",
            "README.md": r"burn COFP.*Credits.*10 Cr per COFP",
            "CONSTITUTION.md": r"burn COFP.*Credits.*10 Cr per COFP",
            "blockchain/README.md": r"burn COFP.*Credits.*10 Cr per COFP",
        },
    ),
    (
        "Consumer rate: 20 Cr per 1 COP",
        {
            "coffeepie_backend/payments/models.py": r"20 Cr.*1 COP|cr // 20",
        },
    ),
]


def check_file(file_relpath: str, pattern: str) -> bool:
    """Check if pattern matches anywhere in the file."""
    path = ROOT / file_relpath
    if not path.exists():
        print(f"  ⚠ MISSING FILE: {file_relpath}")
        return False

    content = path.read_text(encoding="utf-8")

    # Special: negative check — pattern should NOT match
    if pattern.startswith("^((") and "))" in pattern:
        # This is a "must NOT contain" check
        # Extract the inner pattern from ^((?!INNER).)*$
        inner_match = re.search(r"\(\?!(.+?)\)", pattern)
        if inner_match:
            inner = inner_match.group(1)
            if re.search(inner, content, re.IGNORECASE | re.MULTILINE):
                print(f"  ✗ {file_relpath}: FORBIDDEN pattern found: {inner}")
                return False
            return True

    # Normal: pattern MUST match
    if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
        return True
    else:
        print(f"  ✗ {file_relpath}: pattern NOT found")
        print(f"    Expected: {pattern}")
        return False


def main() -> int:
    errors = 0
    warnings = 0

    for description, files in CHECKS:
        print(f"\n[{description}]")
        all_ok = True
        for filepath, pattern in files.items():
            if not check_file(filepath, pattern):
                all_ok = False
                errors += 1
        if all_ok:
            print("  ✓")

    print(f"\n{'='*60}")
    if errors == 0:
        print("ALL CHECKS PASSED — documentation is coherent.")
        return 0
    else:
        print(f"FAILED: {errors} check(s) found inconsistencies.")
        print("Fix the above before merging. Policy docs must agree.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
