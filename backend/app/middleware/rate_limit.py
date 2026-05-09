"""Rate limiting middleware — see specs/rate-limiting.md.

At MVP we only enforce the anonymous limit (10/min/IP). Pro (X-API-Key:
pk_*) and B2B (X-API-Key: bk_*) callers are recognised by header prefix
and bypass enforcement — their per-tier limits (60/min and 600/min in
the spec) are stubs we'll wire up alongside Redis in Sprint 2 without
changing the public API.

The key_func returns the API key value when the header starts with the
recognized prefixes; otherwise it falls back to the remote address
(``X-Forwarded-For`` first hop or ``request.client.host``).

The cost_func returns 0 for keyed callers (so each request is a no-op
against the bucket) and 1 for anon callers (so the 10/min ceiling
actually triggers).

A 429 response includes:
- A JSON body matching the spec (RFC-7807-ish shape with our ``code``).
- ``Retry-After`` header in seconds.
- ``X-RateLimit-Limit``, ``X-RateLimit-Remaining`` (always 0 on 429),
  and ``X-RateLimit-Reset`` (unix seconds).
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _is_keyed_caller(request: Request) -> bool:
    api_key = request.headers.get("x-api-key")
    return bool(api_key and api_key.startswith(("pk_", "bk_")))


def _key_func(request: Request) -> str:
    """Identify the caller for bucketing.

    Pro (``pk_*``) and B2B (``bk_*``) keys get their own bucket so they
    don't collide with the anonymous IP bucket. Anything else falls back
    to the remote address (which honors X-Forwarded-For).
    """
    api_key = request.headers.get("x-api-key")
    if api_key and api_key.startswith(("pk_", "bk_")):
        return api_key
    return get_remote_address(request)


def cost_func(request: Request) -> int:
    """Return 0 for callers we don't enforce limits on at MVP.

    Per the spec ("API key tiers are stubs at MVP — at this stage we
    only enforce the anonymous limit"), Pro/B2B keys bypass the per-IP
    ceiling. We do this by making each of their requests cost 0 against
    the bucket, which slowapi treats as 'never blocks'. Anonymous
    callers cost 1 per request and hit the 10/min wall.
    """
    return 0 if _is_keyed_caller(request) else 1


# default_limits is empty: each route opts in via ``@limiter.limit(...)``.
limiter = Limiter(key_func=_key_func, default_limits=[])


def rate_limit_exception_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Render a 429 with the spec'd JSON body and headers."""
    # ``exc.limit`` is a slowapi.wrappers.Limit. ``exc.limit.limit`` is
    # the underlying limits.RateLimitItem (where ``.amount`` lives).
    limit_item = exc.limit.limit
    limit_amount = getattr(limit_item, "amount", 0)

    # Best-effort lookup of the window stats for accurate reset/remaining.
    # ``view_rate_limit`` is set by slowapi when it evaluates the route.
    reset_unix = int(time.time()) + 60  # safe default — 1 minute window
    remaining = 0
    try:
        view_rl = getattr(request.state, "view_rate_limit", None)
        if view_rl is not None:
            window_stats = limiter.limiter.get_window_stats(view_rl[0], *view_rl[1])
            reset_unix = int(window_stats[0])
            remaining = int(window_stats[1])
    except Exception:  # noqa: BLE001 — telemetry only, never break the response
        pass

    retry_after_s = max(1, reset_unix - int(time.time()))
    reset_at_iso = (
        datetime.fromtimestamp(reset_unix, tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )

    body = {
        "type": "https://propcheck.in/errors/rate-limited",
        "title": "Rate limited",
        "status": 429,
        "detail": f"Too many requests. Try again in {retry_after_s}s.",
        "code": "RATE_LIMITED",
        "limit": limit_amount,
        "remaining": remaining,
        "reset_at": reset_at_iso,
    }

    headers = {
        "Retry-After": str(retry_after_s),
        "X-RateLimit-Limit": str(limit_amount),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_unix),
    }

    return JSONResponse(status_code=429, content=body, headers=headers)


__all__ = ["limiter", "rate_limit_exception_handler"]
