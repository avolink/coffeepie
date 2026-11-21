"""Tiny in-memory rate limiter for the authentication routes.

Sliding window per (bucket, client IP). In-memory and per-process: enough to
stop password guessing against one instance; for several workers put the same
rule in the reverse proxy (nginx limit_req) or move this to Redis.

Behind a proxy, run uvicorn with --proxy-headers --forwarded-allow-ips=<proxy>
so request.client.host is the visitor, not nginx.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_hits = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(bucket: str, limit: int, window_seconds: int):
    """FastAPI dependency: at most `limit` calls per `window_seconds` per IP."""
    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        key = (bucket, ip)
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many attempts, try again later",
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)
    return dependency


def reset():
    """For tests."""
    with _lock:
        _hits.clear()
