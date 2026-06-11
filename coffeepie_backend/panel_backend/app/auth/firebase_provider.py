"""Firebase identity provider — prototyping only (being migrated to Supabase).

Implements the same IdentityProvider interface as Supabase so the two are
interchangeable. Roles live in a top-level `roles` custom claim.
"""

from __future__ import annotations

import os

from app.auth.identity import AuthenticatedUser, IdentityError


class FirebaseIdentityProvider:
    name = "firebase"

    def __init__(self) -> None:
        self._initialized = False

    def _ensure(self) -> None:
        if self._initialized:
            return
        import firebase_admin
        from firebase_admin import credentials

        if not firebase_admin._apps:
            cred_path = os.getenv(
                "FIREBASE_ADMIN_SDK_JSON", "app/secrets/firebase-adminsdk.json"
            )
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(
                cred, {"projectId": os.getenv("FIREBASE_PROJECT_ID")}
            )
        self._initialized = True

    def verify(self, token: str) -> AuthenticatedUser:
        self._ensure()
        from firebase_admin import auth

        try:
            decoded = auth.verify_id_token(token)
        except Exception as e:
            raise IdentityError(f"firebase token rejected: {e}") from e

        roles = decoded.get("roles") or []
        if isinstance(roles, str):
            roles = [roles]
        uid = decoded.get("uid") or decoded.get("user_id")
        if not uid:
            raise IdentityError("firebase token missing uid")

        return AuthenticatedUser(
            uid=uid,
            email=decoded.get("email"),
            roles=list(roles),
            issuer=self.name,
            claims=decoded,
        )

    def set_user_roles(self, uid: str, roles: list[str]) -> None:
        """Admin helper: set the `roles` custom claim (Firebase-specific).

        Supabase's equivalent is updating `app_metadata.roles` via the
        service-role admin API — see README role-assignment note.
        """
        self._ensure()
        from firebase_admin import auth

        existing = auth.get_user(uid).custom_claims or {}
        existing["roles"] = roles
        auth.set_custom_user_claims(uid, existing)
