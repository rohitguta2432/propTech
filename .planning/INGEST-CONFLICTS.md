# Ingest Conflicts

> Generated 2026-05-09 during manual `.planning/` bootstrap from existing specs.

### BLOCKERS (0)

_None._ No `LOCKED-vs-LOCKED` ADR-level contradictions surfaced.

### WARNINGS (3)

These are competing variants where multiple sources disagreed; resolved by taking the authoritative one (live-deploy state + most recent sprint-1.md updates). Listed here for transparency.

| # | Topic | Variants | Chosen | Rationale |
|---|---|---|---|---|
| 1 | Backend host | Specs: Railway. Live: Vercel @vercel/python. | **Vercel for v0.1, Railway in Phase 7** | Live deploy state. Phase 7 covers the migration. |
| 2 | Domain | Specs: `propcheck.in`. Live: `propcheck.rohitraj.tech`. | **rohitraj.tech subdomains for v0.1** | Founder used personal Vercel domain to avoid registrar friction at MVP. Real domain after brand lock. |
| 3 | Trust signal count | Spec lists 11 signals. Trust engine wires 6. | **6 wired + 5 deferred** | `specs/sprint-1.md` Day 7 + Day 8 status notes are authoritative. The 5 deferred signals (DUPLICATE_LISTING, STOLEN_PHOTOS active, IMAGE_DEDUP_OK, BUILDER_COMPLAINTS, LISTING_FRESH) are tracked as REQ-016..018 with pending status. |

### INFO (0)

_None._

---

**Auto-resolved**: 3 conflicts, all warnings. No human action required to proceed.
