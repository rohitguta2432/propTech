# STATE

> Project memory. Updated whenever a phase completes or a major decision lands.

**Last updated**: 2026-05-09
**Current milestone**: v0.1 — MVP launch
**Current phase**: 5 (feedback shipped) → 6 (calibration, blocked on real URLs) / 7 (real scrapes, blocked on Railway)

## Live URLs

| Surface | URL | Status |
|---|---|---|
| Frontend | https://propcheck.rohitraj.tech | ✅ |
| API | https://api.rohitraj.tech | ✅ |
| GitHub | https://github.com/rohitguta2432/propTech | synced |

## Tech footprint

- Backend: FastAPI on Vercel (project `propcheck-api`). Python 3.11.
- Frontend: Next.js 14 on Vercel (project `propcheck-app`).
- Database: Supabase Postgres (Singapore, Session pooler). 8 tables migrated, 400+ locality_prices rows seeded.
- LLM parsing fallback: Gemma 4 31B via OpenRouter free tier — `app/integrations/llm_parser.py`. **`OPENROUTER_API_KEY` set in Vercel (production + development) on 2026-05-09 and verified live**: Gemma 4 31B correctly parses ₹1.2 Cr → 12000000 on test HTML. Used only to fill gaps in regex-parsed listing fields; never participates in scoring. Note: free-tier Gemma can be intermittently rate-limited upstream by Google AI Studio — failures are silent (regex result returned unchanged), so the system never breaks.
- Auth: none at MVP.
- Tests: 88/88 pass via pytest. GitHub Actions CI on push/PR.

## Phase status

| Phase | Status |
|---|---|
| 1 Foundation | ✅ DONE |
| 2 Scrapers + integrations | ✅ DONE |
| 3 Trust engine v1 | ✅ DONE |
| 4 Hardening + ops | ✅ DONE |
| 5 Feedback + observability | ✅ feedback done; observability pending Sentry/PostHog signup |
| 6 Calibration | ⏳ blocked on user-supplied real URLs |
| 7 Real scrapes from production | ⏳ blocked on Railway/Fly migration |
| 8 Chrome extension | ✅ DONE — built locally, awaiting Chrome Web Store publish ($5 one-time) |
| 9 WhatsApp bot | 🅿️ parked (out of stock) — Chrome extension covers same distribution; revisit on user demand |
| 10 Auth + Pro/B2B keys | 🚧 planned |
| 11 Multi-state RERA + cities | 🚧 partial (Karnataka + Maharashtra done) |

## Recent commits (most recent first)

- `7301731` sprint 1 day 12 + multi-state + locality expansion + legal pages + ops
- `54cd034` frontend: add /how-it-works and /for-lenders pages
- `f249c4a` sprint 1 days 8 + 11: image hash + rate limiting
- `ff5e135` sprint-1: mark days 5-7 + 9 done
- `63da585` sprint 1 days 5-9 + day 13: real signals end-to-end

## Open decisions (waiting on founder)

1. Final brand name (PropCheck is working) and domain registration.
2. Real-scrape strategy: Railway+proxies vs Firecrawl vs accept-stub.
3. Sentry + PostHog signup (wiring docs are ready in `docs/MONITORING.md`).
4. Ten real-listing URLs for calibration (5 clean, 5 suspicious).
5. Lawyer review of `/privacy` and `/terms` before any commercial pilot.

## Outstanding tech debt / known issues

- `docs/MONITORING.md` describes Sentry/PostHog wiring but neither is active.
- `STOLEN_PHOTOS` signal: image-hash module shipped but trust engine doesn't yet emit it (waits on real scrapes giving us actual photos to hash).
- Trust engine RERA descriptions still say "Karnataka" even when Maharashtra dispatcher is used; minor copy fix.
- Local Windows OG image generation broken; static OG.png pending.
- No production analytics — flying blind on user behaviour.

## Session continuity

When resuming work, run `/gsd-progress` to see the next logical action.
