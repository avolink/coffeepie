"""Encryption for a node's root credentials (db/01_schema.sql: node.root_password_enc).

The Orchestrator/Broker needs the ACTUAL root password back to log into the
node and provision instances, so this is REVERSIBLE encryption (Fernet:
AES-128-CBC + HMAC-SHA256) — not a one-way password hash like
app/auth/qa_passwords.py.

NODE_CRED_ENC_KEY must be a urlsafe-base64 32-byte Fernet key in production
(generate with `Fernet.generate_key()`) and must never change without
re-encrypting stored rows. QA/dev falls back to a fixed, publicly-known key —
never rely on that default outside QA.
"""

import os

from cryptography.fernet import Fernet, InvalidToken

_QA_DEFAULT_KEY = b"ZVqh3DooH0vtHasv_SRjBQH3wJ0I9pDZYWNglQg2qJE="

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.getenv("NODE_CRED_ENC_KEY", "").encode() or _QA_DEFAULT_KEY
        _fernet = Fernet(key)
    return _fernet


def encrypt_password(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str | None:
    """Returns None if the ciphertext can't be decrypted with the current key."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None
