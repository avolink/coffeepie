"""PBKDF2 password verification for QA-local auth (stdlib only, no extra deps).

Hash format: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>
Matches db/03_qa_auth.sql. QA-only — production auth is Supabase (no passwords).
"""

import hashlib
import hmac


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
