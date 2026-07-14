"""Panel backend configuration and the identity-provider factory.

AUTH_PROVIDER selects the IdP, defaulting to "both" to match the roadmap's
Firebase→Supabase migration window (accept either token). Set it to "supabase"
once the cutover completes.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from app.auth.identity import CompositeIdentityProvider, IdentityProvider

# "supabase" | "firebase" | "both"
AUTH_PROVIDER = os.getenv("AUTH_PROVIDER", "both").lower()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def _as_bool(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


# QA-only local login (db/03_qa_auth.sql + /auth/login). MUST stay false in prod.
QA_LOCAL_AUTH = _as_bool(os.getenv("QA_LOCAL_AUTH"))

# CORS origins allowed to call this API (comma-separated). Production domain +
# the old Firebase prototype origin (still may be live) + localhost for QA.
# Never use "*" with credentials.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        # Production + deployed prototype + local Firebase serve (:5000) + local static serve (:8080).
        "https://coffeepie.co,https://www.coffeepie.co,"
        "https://coffeepie-firebase.web.app,"
        "http://localhost:5000,http://127.0.0.1:5000,"
        "http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if o.strip()
]

_provider_singleton: IdentityProvider | None = None


def _build_supabase() -> IdentityProvider:
    from app.auth.supabase_provider import SupabaseIdentityProvider

    return SupabaseIdentityProvider(url=SUPABASE_URL, jwt_secret=SUPABASE_JWT_SECRET)


def _build_firebase() -> IdentityProvider:
    from app.auth.firebase_provider import FirebaseIdentityProvider

    return FirebaseIdentityProvider()


def get_identity_provider() -> IdentityProvider:
    """Return the configured identity provider (cached)."""
    global _provider_singleton
    if _provider_singleton is not None:
        return _provider_singleton

    if AUTH_PROVIDER == "supabase":
        _provider_singleton = _build_supabase()
    elif AUTH_PROVIDER == "firebase":
        _provider_singleton = _build_firebase()
    else:  # "both" — prefer Supabase, fall back to Firebase during migration
        _provider_singleton = CompositeIdentityProvider(
            [_build_supabase(), _build_firebase()]
        )
    return _provider_singleton
