# ROADMAP

Phases for **Milestone v0.1 — MVP launch**.

| Phase | Name | Status | Notes |
|---|---|---|---|
| 1 | Foundation | ✅ DONE | Sprint 1 Days 1–4. Repo + Postgres + Alembic + URL parsers + `/v1/check` skeleton. |
| 2 | Scrapers + integrations | ✅ DONE | Sprint 1 Days 5–9. Magicbricks + 99acres scrapers; Karnataka + Maharashtra RERA dispatcher; image hash module; Bangalore/Mumbai/Delhi/Pune/Hyderabad locality prices (~400 rows). |
| 3 | Trust engine v1 | ✅ DONE | Sprint 1 Day 7. RERA + price + age signals wired. Image hash module exists but trust engine doesn't yet emit `STOLEN_PHOTOS` flag (waits on real scrapes). |
| 4 | Hardening + ops | ✅ DONE | Sprint 1 Days 10–11 + legal: rate limiting, 24h DB cache, privacy/terms/about/404, sitemap, robots, GitHub Actions CI, monitoring docs. |
| 5 | Feedback + observability | ✅ DONE (feedback) / ⏳ partial | `POST /v1/feedback` shipped. Sentry + PostHog wiring documented in `docs/MONITORING.md`; awaiting account signup. |
| 6 | Calibration | ⏳ BLOCKED | Sprint 1 Day 14. Need 10 hand-picked real listing URLs (5 known-clean, 5 known-suspicious) to score and tune deltas. |
| 7 | Real scrapes from production | ⏳ BLOCKED | Vercel egress blocked by portal anti-bot. Migrate backend to Railway / Fly + add residential proxy (Bright Data) OR proxy via Firecrawl. Needs Railway account. |
| 8 | Chrome extension | 🚧 PLANNED | The viral surface. Spec already in `specs/design.md`. Build: Manifest V3 content script overlaying score badge on portal listing cards. Chrome Web Store listing. ~2–3 days. |
| 9 | WhatsApp bot | 🚧 PLANNED | Forward-a-link flow via Twilio. ~1–2 days. |
| 10 | Auth + Pro/B2B keys | 🚧 PLANNED | Stripe-backed signup, key issuance, per-tier metering. ~3–5 days. |
| 11 | Multi-state RERA + cities | 🚧 PARTIAL / IN-PROGRESS | Karnataka + Maharashtra live. Add Delhi (RERA Delhi), Haryana (HARERA), Tamil Nadu, Telangana. Each ~1 day. |

## Out of scope at v0.1

- Real Google Vision reverse-image search (deferred until Vercel→Railway migration).
- Mobile native apps (web + extension + WhatsApp covers ~95% of usage).
- Commercial property / land / plots (residential only at launch).
- Title-deed verification (we partner with Landeed for that).
- Multi-language UI (English only at launch; Hindi later).

## Dependencies

```
Phase 7 (Real scrapes)  → unblocks Phase 6 (Calibration with real data)
Phase 7 + Phase 8      → makes Chrome extension actually score real listings live
Phase 10 (Auth)         → unblocks first paid B2B contract
```

## Cadence

We've been running ad-hoc sprints (1–3 day chunks). Recommended cadence going forward:
- 1 phase = 1 week of focused work + 1 day of integration/testing/deploy.
- Use `/gsd-plan-phase N` to break each into concrete tasks.
- Use `/gsd-execute-phase N` once a plan exists.
