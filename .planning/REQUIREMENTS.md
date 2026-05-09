# REQUIREMENTS

Source: synthesised from `README.md`, `specs/*.md`, `90-day-plan.md`, `landing-page.md`.

## Functional requirements

### Consumer-facing (free tier)

- **REQ-001** — A user can paste any URL from Magicbricks, 99acres, Housing.com, or NoBroker into the web tool and receive a 0–100 Trust Score within 30 seconds. (Phase 1 ✅)
- **REQ-002** — Trust Score includes red flags, green flags, a pre-purchase checklist, and a verifications data table — every claim cites a source. (Phase 3 ✅)
- **REQ-003** — Same URL re-checked within 24 hours returns the cached report instantly with `cache_hit: true`. (Phase 4 ✅)
- **REQ-004** — User can flag a wrong score via `POST /v1/feedback` and we acknowledge with status=pending. (Phase 5 ✅)
- **REQ-005** — Rate limit: anonymous users capped at 10 checks/minute/IP; 11+ returns 429 with the spec'd JSON body and `Retry-After` header. (Phase 4 ✅)
- **REQ-006** — Score bands: ≥70 safe (green), 40–69 caution (amber), <40 risky (red). Visual treatment matches `specs/design.md`. (Phase 3 ✅)
- **REQ-007** — `/how-it-works`, `/for-lenders`, `/about`, `/privacy`, `/terms`, `/not-found` (custom 404), `/robots.txt`, `/sitemap.xml` — all routable. (Phase 4 ✅)

### Trust engine signals

- **REQ-010** — `RERA_MATCH` (+10) when the listed RERA ID matches a registered project in the relevant state registry. (Phase 3 ✅)
- **REQ-011** — `RERA_MISMATCH` (-25) when the listed RERA ID doesn't match any record. (Phase 3 ✅)
- **REQ-012** — `RERA_MISSING` (-10) when no RERA ID is on the listing AND `area_sqft >= 800`. (Phase 3 ✅)
- **REQ-013** — `PRICE_BELOW_MARKET` (-10) when ≤-15% vs locality avg ₹/sqft for that BHK. (Phase 3 ✅)
- **REQ-014** — `PRICE_ABOVE_MARKET` (-5) when ≥+25%. (Phase 3 ✅)
- **REQ-015** — `LISTING_STALE` (-5) when listing age >180 days. (Phase 3 ✅)
- **REQ-016** — `STOLEN_PHOTOS` (-25) when listing photos appear on ≥3 unrelated listings. (Module exists; not yet emitted by trust engine — needs working scrape.)
- **REQ-017** — `DUPLICATE_LISTING` (-15 to -25) when the same property is listed across multiple portals at different prices. (Pending — wait for cross-portal scrape data.)
- **REQ-018** — `BUILDER_COMPLAINTS` (-5 / -10 / -20) by complaint count. (Pending — needs builder reputation index.)

### Integrations

- **REQ-020** — Karnataka RERA verification with 7-day cache. (Phase 2 ✅)
- **REQ-021** — Maharashtra RERA verification with 7-day cache. (Phase 2 ✅)
- **REQ-022** — Locality price index for 7 cities (Bangalore + Mumbai + Delhi + Gurgaon + Noida + Pune + Hyderabad), ~400 rows. (Phase 2 ✅)
- **REQ-023** — Perceptual image hash + Hamming-distance dedup. (Phase 2 ✅)

### B2B API

- **REQ-030** — `POST /v1/check` endpoint with same response schema for free + paid. (Phase 1 ✅)
- **REQ-031** — Pro keys (`pk_*`) and B2B keys (`bk_*`) bypass the anonymous rate limit via cost-func=0. (Phase 4 ✅)
- **REQ-032** — Per-key rate limits + per-key billing meter. (Pending — Phase 10.)
- **REQ-033** — OpenAPI / Swagger UI auto-generated at `/docs`. (Phase 1 ✅, FastAPI default.)

### Operations

- **REQ-040** — All endpoints respond with `X-RateLimit-Limit/Remaining/Reset` headers. (Phase 4 ✅)
- **REQ-041** — `/healthz` is never rate-limited. (Phase 4 ✅)
- **REQ-042** — `pytest tests/` passes on every push to main via GitHub Actions. (Phase 4 ✅)
- **REQ-043** — Frontend Next.js build passes on every push. (Phase 4 ✅)
- **REQ-044** — Backend errors visible in production via Sentry. (Pending — `docs/MONITORING.md` documents the wiring; needs Sentry signup.)

## Non-functional requirements

- **NFR-001** — `/v1/check` P50 latency <500ms (cached), P99 <1s.
- **NFR-002** — Frontend hero LCP <2s on 3G.
- **NFR-003** — Mobile-first: every page works on 375×812 viewport.
- **NFR-004** — WCAG AA color contrast on all text. Score colors include text label, never colour alone.
- **NFR-005** — All scrapers fail-soft (never raise to caller). Fetch failures produce a `ScrapedListing` with `fetch_error` set.
- **NFR-006** — Database writes for `/v1/check` are best-effort: a DB outage doesn't block returning a score.
- **NFR-007** — All HTTP calls have a 5–6s timeout to fit Vercel's 10s serverless ceiling.
- **NFR-008** — Privacy: no PII storage at MVP. Only URLs, /24-truncated IPs, user-agent strings.

## Compliance / legal

- **REQ-050** — Privacy Policy and Terms of Service published before any commercial pilot. (Phase 4 ✅, pending lawyer review.)
- **REQ-051** — Indian DPDP Act 2023 compliance for any Indian-resident user data. (Pending — review with lawyer.)
