# Synthesis

> Bootstrap-time synthesis of pre-existing planning docs into the GSD planning model. Created 2026-05-09.

## Source documents ingested

| Path | Type | Role in synthesis |
|---|---|---|
| `README.md` | DOC | Product idea, audience, monetisation → `PROJECT.md` |
| `90-day-plan.md` | PRD | Sprint cadence, MVP scope, target metrics → `ROADMAP.md` |
| `positioning.md` | DOC | Brand voice, name candidates, audience segments → `PROJECT.md` (working name) |
| `landing-page.md` | DOC | UX copy, FAQ, CTAs → REQ-001/002 narrative |
| `specs/architecture.md` | SPEC | System design, components, deployment topology → `PROJECT.md` (locked decisions) + REQ-040..043 |
| `specs/design.md` | SPEC | Visual identity, screen wireframes, component library → REQ-006 + NFR-003/004 |
| `specs/database.md` | SPEC | Postgres schema, retention → REQ-003 backing |
| `specs/api.md` | SPEC | Endpoint contracts, error format, rate limits → REQ-001 + REQ-005 + REQ-030..033 |
| `specs/trust-engine.md` | SPEC | 11-signal scoring rules + calibration targets → REQ-010..018 |
| `specs/scrapers.md` | SPEC | Per-portal scraping interface → REQ-001 backing + NFR-005/007 |
| `specs/integrations.md` | SPEC | RERA + locality + image hash modules → REQ-020..023 |
| `specs/multi-state-rera.md` | SPEC | RERA dispatcher pattern → REQ-021 |
| `specs/rate-limiting.md` | SPEC | 429 contract + slowapi wiring → REQ-005 + REQ-031 |
| `specs/sprint-1.md` | DOC (roadmap-shaped) | Phase status (Days 1–14) → `ROADMAP.md` + `STATE.md` |
| `backend/README.md` | DOC | Local dev setup → no requirement; informational |
| `docs/MONITORING.md` | DOC | Sentry/PostHog wiring instructions → REQ-044 (deferred) |

## Auto-resolved

- **Domain naming** — `propcheck.in` mentioned aspirationally in some specs; actual deployment uses `propcheck.rohitraj.tech` and `api.rohitraj.tech`. Resolution: locked decision in `PROJECT.md` is the deployed subdomains; aspirational `.in` domain is an open decision.
- **Backend hosting** — multiple specs mention Railway as the long-term host; current deployment is Vercel @vercel/python. Resolution: locked decision is Vercel-for-now-Railway-later, with Phase 7 covering the migration.
- **Trust engine signal count** — spec says 11 signals; trust engine v1 wires 6. Resolution: requirements list all 11 with status (DONE / pending) so nothing is lost; trust-engine.md remains the source of truth for signal definitions.

## No conflicts

No `LOCKED-vs-LOCKED` ADR contradictions surfaced. The three competing-variant cases above were resolvable from authoritative sources (live deploy state, sprint-1.md status notes).

## Notes for future planners

- `specs/sprint-1.md` is the canonical day-by-day execution log. Treat it as the source of truth when reconciling phase status.
- The repo has both a top-level `specs/` folder AND a `.planning/` folder (this one). Going forward: `specs/` holds technical contracts (API shapes, schemas, signal definitions); `.planning/` holds GSD project artifacts (PROJECT, ROADMAP, REQUIREMENTS, STATE). They're complementary, not duplicative.
- Multiple agent-built features (image hash, MahaRERA dispatcher) shipped via parallel `superpowers-dispatching-parallel-agents` invocations; each agent wrote its own tests and updated specs.
- 78/78 tests pass as of 2026-05-09; CI runs them on every push.
