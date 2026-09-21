"""Minimal Postgres access for the panel backend.

Production uses **psycopg3** (DATABASE_URL). Both psycopg and the pure-Python
**pg8000** speak DB-API 2.0 with `%s` placeholders, so the query code in the rest
of the app is identical regardless of driver. We prefer psycopg and fall back to
pg8000 when psycopg isn't installed (e.g. environments without libpq / very new
Python without binary wheels). Set PANEL_DB_DRIVER=psycopg|pg8000 to force one.

Kept deliberately small — this backs QA auth lookups today; the durable
LedgerRepository (the partner's #1 task) will build on the same connection.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from urllib.parse import urlparse


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "coffeepie")
    pw = os.getenv("POSTGRES_PASSWORD", "coffeepie_dev")
    db = os.getenv("POSTGRES_DB", "coffeepie")
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{pw}@{host}:{port}/{db}"


def _driver() -> str:
    forced = os.getenv("PANEL_DB_DRIVER")
    if forced:
        return forced
    try:
        import psycopg  # noqa: F401

        return "psycopg"
    except ImportError:
        return "pg8000"


@contextmanager
def get_conn():
    """Yield a short-lived DB-API connection. Caller manages the transaction."""
    driver = _driver()
    if driver == "psycopg":
        import psycopg

        conn = psycopg.connect(database_url())
    else:
        import pg8000.dbapi

        u = urlparse(database_url())
        conn = pg8000.dbapi.connect(
            user=u.username,
            password=u.password,
            host=u.hostname or "127.0.0.1",
            port=u.port or 5432,
            database=(u.path or "/").lstrip("/"),
        )
    try:
        yield conn
    finally:
        conn.close()
