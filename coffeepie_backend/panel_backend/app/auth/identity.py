"""Provider-agnostic identity layer.

Per AGENTS.md ("Supabase for Identity & Backend services, replacing Firebase")
and ROADMAP.json (graceful migration period accepting both), the panel backend
must not hard-wire a single IdP. Auth verification sits behind `IdentityProvider`
so Firebase (prototype) and Supabase (production, self-hostable, sovereign) are
interchangeable — selected by config, never imported directly by business logic.

Every provider normalizes its token into the same `AuthenticatedUser`, so RBAC
and the routes are identical regardless of who issued the token.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class IdentityError(Exception):
    """Raised when a token cannot be verified by a provider."""


class Role(str, Enum):
    """Coffee Pie panel roles. Pure domain — no web-framework coupling, so it is
    testable and reusable outside the HTTP layer."""

    ADVERTISER = "advertiser"        # main clients — campaigns, segments, assets
    MANUFACTURER = "manufacturer"    # terminal makers — QFDM licenses
    PROVIDER = "provider"            # register nodes, earn COFP for served slices
    CONTRIBUTOR = "contributor"      # hold COFP, vote on technical decisions
    ADMIN = "admin"                  # platform operators


@dataclass
class AuthenticatedUser:
    """Normalized identity, independent of the issuing IdP."""
    uid: str
    email: str | None
    roles: list[str]            # raw role strings; RBAC maps these to Role enum
    issuer: str                 # which provider validated this ("firebase"/"supabase")
    claims: dict = field(default_factory=dict)


def roles_of(user: "AuthenticatedUser") -> set[Role]:
    """Map a user's raw role strings to the Role enum (unknown strings ignored,
    keeping the mapping forward-compatible with roles a newer IdP may add)."""
    out: set[Role] = set()
    for r in user.roles:
        try:
            out.add(Role(r))
        except ValueError:
            continue
    return out


@runtime_checkable
class IdentityProvider(Protocol):
    name: str

    def verify(self, token: str) -> AuthenticatedUser:
        """Verify a bearer token or raise IdentityError."""
        ...


class CompositeIdentityProvider:
    """Tries each provider in order — the roadmap's migration window.

    During the Firebase→Supabase cutover, tokens from either IdP are accepted.
    Order matters: put the *target* provider (Supabase) first so it's preferred
    once users start getting Supabase tokens.
    """

    name = "composite"

    def __init__(self, providers: list[IdentityProvider]) -> None:
        if not providers:
            raise ValueError("CompositeIdentityProvider needs at least one provider")
        self._providers = providers

    def verify(self, token: str) -> AuthenticatedUser:
        last: Exception | None = None
        for p in self._providers:
            try:
                return p.verify(token)
            except IdentityError as e:
                last = e
                continue
        raise IdentityError(
            f"no configured identity provider accepted the token "
            f"({', '.join(p.name for p in self._providers)})"
        ) from last
