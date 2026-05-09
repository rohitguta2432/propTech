# Specs

Technical specifications for the PropCheck product. Read these before writing any code.

| Spec | Covers |
|---|---|
| [architecture.md](architecture.md) | System design, components, data flow, deployment topology, security, scaling plan, cost estimates |
| [design.md](design.md) | Visual identity (colors, typography, voice), Trust Score Badge spec, all screen wireframes, component library, mobile and accessibility rules |
| [database.md](database.md) | Postgres schema — every table with CREATE statements, indexes, retention policy |
| [api.md](api.md) | Full API contract — endpoints, request/response shapes, errors, rate limits, versioning |
| [trust-engine.md](trust-engine.md) | Scoring rules v1 — 11 signals, deltas, aggregation formula, calibration targets |
| [sprint-1.md](sprint-1.md) | First 14-day development plan with daily tasks and definition of done |

## Conventions

- Each spec is the **source of truth** for its area. If code disagrees with the spec, the spec wins until the spec is updated by PR.
- Update specs in the same PR as the code that changes them. Don't let them drift.
- Add a new spec file (e.g., `b2b-api.md`, `data-pipeline.md`, `rera-integrations.md`) before building a major new system, not after.

## Status

- **Last updated**: 2026-05-09
- **Stage**: Pre-MVP. Specs ahead of any code.
- **Owner**: Rohit Raj
