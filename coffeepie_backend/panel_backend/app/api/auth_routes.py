"""QA-only local login.

⚠️  Active ONLY when QA_LOCAL_AUTH=true. Lets QA validate the prototype login
end-to-end against the test DB without standing up Supabase/Firebase.

It mints a Supabase-SHAPED HS256 JWT (sub, email, aud=authenticated,
app_metadata.roles) signed with SUPABASE_JWT_SECRET. That means the SAME
SupabaseIdentityProvider that runs in production validates these tokens — there
is no separate QA auth path on the API. Flip QA_LOCAL_AUTH off and this issuer is
gone; real Supabase tokens keep working unchanged.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from app import config
from app.auth.qa_passwords import verify_password
from app.db import get_conn
from app.models.panel_models import LoginIn, LoginOut

router = APIRouter(prefix="/auth", tags=["auth"])

_TOKEN_TTL_SECONDS = 12 * 3600


def _load_user(email: str):
    """Return (uid, email, password_hash, roles) or None.

    Uses explicit cursor close (not `with conn.cursor()`) so it works across both
    psycopg and pg8000 — DB-API 2.0 does not require cursors to be context
    managers, and pg8000's are not.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT u.id::text, u.email, c.password_hash
                FROM app_user u
                JOIN qa_credential c ON c.user_id = u.id
                WHERE lower(u.email) = lower(%s)
                """,
                (email,),
            )
            row = cur.fetchone()
            if not row:
                return None
            uid, em, pw_hash = row
            cur.execute("SELECT role FROM user_role WHERE user_id = %s", (uid,))
            roles = [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
    return uid, em, pw_hash, roles


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn):
    if not config.QA_LOCAL_AUTH:
        # Defensive: router is only mounted when enabled, but never 200 here.
        raise HTTPException(status_code=404, detail="Not found")
    if not config.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="QA login needs SUPABASE_JWT_SECRET set (token signing key).",
        )

    import jwt

    user = _load_user(body.email)
    # Verify even on miss-shaped input to keep timing uniform-ish.
    placeholder = "pbkdf2_sha256$100000$00$00"
    if user is None:
        verify_password(body.password, placeholder)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    uid, email, pw_hash, roles = user
    if not verify_password(body.password, pw_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    now = int(time.time())
    claims = {
        "sub": uid,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": {"roles": roles},
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
    }
    token = jwt.encode(claims, config.SUPABASE_JWT_SECRET, algorithm="HS256")
    return LoginOut(access_token=token, uid=uid, email=email, roles=roles)
