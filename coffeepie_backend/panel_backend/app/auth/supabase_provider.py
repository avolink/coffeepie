"""Supabase identity provider — production IAM.

Supabase issues a standard JWT. We verify it locally (no network round-trip on
the hot path) and read app roles from `app_metadata.roles`.

`app_metadata` is the correct place for authorization: it is writable only with
the service-role key (never by the user), unlike `user_metadata`. The top-level
`role` claim is the *Postgres* role (anon/authenticated) and is NOT used for app
authorization here.

Two verification modes, auto-selected:
  * `SUPABASE_JWT_SECRET` set  → HS256 with the shared secret (legacy projects).
  * otherwise                  → JWKS from `${SUPABASE_URL}/auth/v1/.well-known/
                                  jwks.json` (asymmetric ES256/RS256, current
                                  Supabase default; keys can be rotated).
Both work against self-hosted Supabase, preserving sovereignty.
"""

from __future__ import annotations

import os

from app.auth.identity import AuthenticatedUser, IdentityError

# Supabase sets aud="authenticated" for logged-in users.
_EXPECTED_AUDIENCE = "authenticated"


class SupabaseIdentityProvider:
    name = "supabase"

    def __init__(self, url: str | None = None, jwt_secret: str | None = None) -> None:
        self.url = (url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        self.secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET")
        self._jwks_client = None  # lazily built PyJWKClient

    def _jwks(self):
        if self._jwks_client is None:
            from jwt import PyJWKClient

            if not self.url:
                raise IdentityError("SUPABASE_URL not set and no SUPABASE_JWT_SECRET")
            self._jwks_client = PyJWKClient(f"{self.url}/auth/v1/.well-known/jwks.json")
        return self._jwks_client

    def verify(self, token: str) -> AuthenticatedUser:
        import jwt

        try:
            if self.secret:
                claims = jwt.decode(
                    token, self.secret, algorithms=["HS256"], audience=_EXPECTED_AUDIENCE
                )
            else:
                signing_key = self._jwks().get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256", "RS256"],
                    audience=_EXPECTED_AUDIENCE,
                )
        except Exception as e:  # jwt.PyJWTError and JWKS/network errors
            raise IdentityError(f"supabase token rejected: {e}") from e

        app_meta = claims.get("app_metadata") or {}
        roles = app_meta.get("roles") or []
        if isinstance(roles, str):
            roles = [roles]

        uid = claims.get("sub")
        if not uid:
            raise IdentityError("supabase token missing 'sub'")

        return AuthenticatedUser(
            uid=uid,
            email=claims.get("email"),
            roles=list(roles),
            issuer=self.name,
            claims=claims,
        )
