"""Tests for the provider-agnostic identity layer + RBAC role mapping.

Pure logic — no network, no real Firebase/Supabase. Run:
  PYTHONPATH=. python -m unittest tests.test_auth
"""

import unittest

from app.auth.identity import (
    AuthenticatedUser,
    CompositeIdentityProvider,
    IdentityError,
    Role,
    roles_of,
)


def _user(roles, issuer="test"):
    return AuthenticatedUser(uid="u1", email="u@x.co", roles=roles, issuer=issuer)


class _OK:
    name = "ok"

    def __init__(self, issuer):
        self._issuer = issuer

    def verify(self, token):
        return _user(["provider"], issuer=self._issuer)


class _Reject:
    name = "reject"

    def verify(self, token):
        raise IdentityError("nope")


class TestComposite(unittest.TestCase):
    def test_prefers_first_provider(self):
        comp = CompositeIdentityProvider([_OK("supabase"), _OK("firebase")])
        self.assertEqual(comp.verify("t").issuer, "supabase")

    def test_falls_back_when_first_rejects(self):
        # Migration window: Supabase rejects a legacy Firebase token → fall back.
        comp = CompositeIdentityProvider([_Reject(), _OK("firebase")])
        self.assertEqual(comp.verify("t").issuer, "firebase")

    def test_raises_when_all_reject(self):
        comp = CompositeIdentityProvider([_Reject(), _Reject()])
        with self.assertRaises(IdentityError):
            comp.verify("t")

    def test_empty_provider_list_is_rejected(self):
        with self.assertRaises(ValueError):
            CompositeIdentityProvider([])


class TestRoleMapping(unittest.TestCase):
    def test_known_roles_map(self):
        self.assertEqual(
            roles_of(_user(["provider", "contributor"])),
            {Role.PROVIDER, Role.CONTRIBUTOR},
        )

    def test_unknown_roles_ignored(self):
        self.assertEqual(roles_of(_user(["provider", "wizard"])), {Role.PROVIDER})

    def test_no_roles(self):
        self.assertEqual(roles_of(_user([])), set())


if __name__ == "__main__":
    unittest.main()
