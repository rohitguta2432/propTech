# Rate Limiting Spec

Protect the public API from runaway clients without blocking real users.

---

## Rules

| Tier | Limit | Identifier |
|---|---|---|
| **Anonymous** (no API key) | **10 requests / minute / IP** | `X-Forwarded-For` first hop, fallback `request.client.host` |
| **Pro** (header `X-API-Key: pk_*`) | 60 / minute / key | the API key |
| **B2B** (header `X-API-Key: bk_*`) | 600 / minute / key | the API key |

(API key tiers are stubs at MVP — at this stage we only enforce the anonymous limit. Recognising the header pattern lets us bypass the global limit later without code churn.)

---

## What gets rate-limited

- `POST /v1/check` (the only expensive endpoint at MVP).
- `POST /v1/feedback`.
- `/healthz` is **never** limited (uptime checks).
- Static surface (Next.js frontend) lives on a different domain — Vercel handles its own DDoS.

---

## Response on 429

```json
{
  "type": "https://propcheck.in/errors/rate-limited",
  "title": "Rate limited",
  "status": 429,
  "detail": "Too many requests. Try again in {retry_after_s}s.",
  "code": "RATE_LIMITED",
  "limit": 10,
  "remaining": 0,
  "reset_at": "2026-05-09T12:35:00Z"
}
```

Headers on **every** response (200 or 429):
- `X-RateLimit-Limit: 10`
- `X-RateLimit-Remaining: 7`
- `X-RateLimit-Reset: 1717059600`  (unix seconds)

On 429 also include `Retry-After: <seconds>`.

---

## Implementation

Use `slowapi` (FastAPI-compatible wrapper around `limits`).

- **Storage backend**: in-memory `MovingWindowRateLimiter` for MVP. Single-instance Vercel functions will share state per warm container; that's acceptable for the anonymous tier (a determined attacker hits multiple containers anyway).
- **When Redis lands** (Sprint 2): swap to `slowapi.RedisRateLimiter` — one config knob, no API change.

Code shape:

```python
# app/middleware/rate_limit.py
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

def _key_func(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    if api_key and api_key.startswith(("pk_", "bk_")):
        return api_key
    return get_remote_address(request)

limiter = Limiter(key_func=_key_func, default_limits=[])
```

Apply on routes:
```python
@router.post("/check")
@limiter.limit("10/minute")
async def submit_check(...): ...
```

In `app/main.py`:
```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

---

## Tests

- `test_under_limit_returns_200` — 9 sequential POSTs from same IP all succeed.
- `test_over_limit_returns_429` — 11th POST returns 429 with proper headers.
- `test_window_resets` — wait 65s, request succeeds again. (Use freezegun or a fake clock.)
- `test_healthz_not_rate_limited` — 50 calls to /healthz never trigger 429.
- `test_pro_key_bypasses_anon_limit` — header `X-API-Key: pk_test` → 11+ requests succeed.

Tests use FastAPI `TestClient` with each test in its own limiter instance to avoid cross-test pollution.

---

## What's explicitly NOT rate-limited

- `/healthz`, `/`, `/docs`, `/openapi.json`.
- Static assets on the frontend domain.

---

## Out of scope at MVP

- IP allow-listing for trusted partners.
- Geo-based throttling.
- Per-route differential limits beyond the table above.
- Distributed rate-limit state (single-instance Vercel works fine until ~1000 RPS).
