"""PBKDF2 password verification for QA-local auth (stdlib only, no extra deps).

Hash format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
Matches db/03_qa_auth.sql. QA-only — production auth is Supabase (no passwords).
"""

import hashlib
import hmac
import secrets


# OWASP Password Storage Cheat Sheet (2023+): 600,000 iterations for
# PBKDF2-HMAC-SHA256. The count is stored in each hash, so hashes made with
# the old 100,000 keep verifying; new and re-set passwords get the new cost.
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex> for storage."""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters_s, salt_hex, hash_hex = encoded.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(dk, expected)  # constant-time


def needs_rehash(encoded: str) -> bool:
    """True when a stored hash uses fewer iterations than today's policy."""
    try:
        return int(encoded.split("$")[1]) < PBKDF2_ITERATIONS
    except (IndexError, ValueError):
        return True
