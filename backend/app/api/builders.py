"""GET /v1/builders/{slug} and /v1/builders/recent.

Every check we run touches a builder. Each builder becomes a permanent,
indexable URL on the website (`/builder/<slug>`) that aggregates:

  - Total checks against this builder's projects on PropCheck
  - Average trust score and a safe/caution/risky breakdown
  - The recent check ids (so each row links to /check/<id>)
  - RERA registrations we know about for them (rera_records)
  - Open complaint counts (builder_complaints)
  - Cities / states the builder is active in

Same compounding-SEO flywheel as /check/<id>: Google picks up "Prestige
Estates RERA complaints", press deep-links to the page as evidence, and
buyers can share a single URL when warning friends about a developer.

Read-only, public, rate-limited.

Implementation note — we walk recent checks in Python and slug-match
there, rather than push the slug normalization into SQL. This is portable
(works on SQLite test engine + Postgres prod), and at v0 volumes the
inner loop is negligible. The natural next step once volume grows is a
materialized `builder_profiles` view or a denormalized `builder_slug`
column on checks; both are mechanical to add later.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.rate_limit import cost_func, limiter
from app.models.db import BuilderComplaint, Check, RERARecord
from app.util.slug import to_slug

router = APIRouter()

# Cap on how many recent checks we surface inside a single builder page —
# keeps the response small and the page scannable.
RECENT_CHECKS_PER_BUILDER = 20

# Cap on slugs returned for sitemap generation. Same shape as /v1/checks/recent.
RECENT_BUILDERS_LIMIT_MAX = 500

# Hard cap on the rows we scan to compute either endpoint. At v0 volumes the
# entire table is well under this, but the cap protects us if volume jumps
# before we add a denormalized builder_slug column.
SCAN_ROWS_CAP = 5_000


@router.get("/builders/recent")
@limiter.limit("30/minute", cost=cost_func)
async def list_recent_builders(
    request: Request,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Recent builder slugs for sitemap generation.

    A builder slug is derivable from any check whose property_data carries
    a builder_name, so we walk recent checks and dedupe by slug. The
    frontend's `sitemap.ts` calls this at revalidate time so every
    `/builder/<slug>` page lands in sitemap.xml.
    """
    limit = max(1, min(RECENT_BUILDERS_LIMIT_MAX, limit))

    rows = (
        db.query(Check.property_data, Check.checked_at)
        .order_by(Check.checked_at.desc())
        .limit(SCAN_ROWS_CAP)
        .all()
    )

    seen: dict[str, str | None] = {}  # slug -> latest checked_at iso
    for prop, checked_at in rows:
        if not isinstance(prop, dict):
            continue
        slug = to_slug(prop.get("builder_name"))
        if not slug or slug in seen:
            continue
        seen[slug] = checked_at.isoformat() if checked_at else None
        if len(seen) >= limit:
            break

    return {
        "items": [{"slug": s, "checked_at": ts} for s, ts in seen.items()],
        "count": len(seen),
    }


@router.get("/builders/{slug}")
@limiter.limit("60/minute", cost=cost_func)
async def get_builder(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Aggregated public profile for one builder.

    404 if no check we've ever run mentions a builder that normalizes to
    this slug. The lookup is slug-based, not exact-name, so "Prestige
    Estates", "PRESTIGE ESTATES PROJECTS LTD", and "prestige-estates" all
    resolve to the same page.
    """
    # Bound the path so a 200-character slug can never become an expensive scan.
    if not slug or len(slug) > 80:
        raise HTTPException(
            status_code=404,
            detail={"code": "BUILDER_NOT_FOUND", "message": "Builder not found."},
        )

    # Scan recent checks; pick out the ones whose builder_name normalizes
    # to the requested slug. We walk newest-first so `recent_checks` is
    # already ordered.
    candidate_rows = (
        db.query(Check)
        .order_by(Check.checked_at.desc())
        .limit(SCAN_ROWS_CAP)
        .all()
    )

    matching: list[Check] = []
    matching_name_counts: Counter[str] = Counter()
    for c in candidate_rows:
        name = (c.property_data or {}).get("builder_name") if isinstance(c.property_data, dict) else None
        if not name:
            continue
        if to_slug(name) == slug:
            matching.append(c)
            matching_name_counts[name] += 1

    if not matching:
        raise HTTPException(
            status_code=404,
            detail={"code": "BUILDER_NOT_FOUND", "message": "Builder not found."},
        )

    matching_names = list(matching_name_counts)
    # Display name = the most-common spelling among matching variants.
    display_name = matching_name_counts.most_common(1)[0][0]

    label_counts = Counter(c.label for c in matching)
    score_values = [c.score for c in matching if c.score is not None]
    avg_score = round(sum(score_values) / len(score_values)) if score_values else None

    cities = sorted(
        {
            (c.property_data or {}).get("city")
            for c in matching
            if (c.property_data or {}).get("city")
        }
    )
    states = sorted(
        {
            (c.property_data or {}).get("state")
            for c in matching
            if (c.property_data or {}).get("state")
        }
    )

    # RERA registrations across all known spellings of this builder.
    rera_rows = (
        db.query(RERARecord)
        .filter(RERARecord.builder_name.in_(matching_names))
        .order_by(RERARecord.fetched_at.desc())
        .all()
    )
    rera_items = [
        {
            "state": r.state,
            "rera_id": r.rera_id,
            "project_name": r.project_name,
            "status": r.status,
        }
        for r in rera_rows
    ]

    # Complaint roll-up across states. A builder often has one row per state.
    complaint_rows = (
        db.query(BuilderComplaint)
        .filter(BuilderComplaint.builder_name.in_(matching_names))
        .all()
    )
    complaints = {
        "open": sum(c.open_count or 0 for c in complaint_rows),
        "closed": sum(c.closed_count or 0 for c in complaint_rows),
        "delays": sum(c.delays_count or 0 for c in complaint_rows),
        "by_state": [
            {
                "state": c.state,
                "open": c.open_count or 0,
                "closed": c.closed_count or 0,
                "delays": c.delays_count or 0,
            }
            for c in complaint_rows
        ],
    }

    recent_checks = [
        {
            "id": c.id,
            "score": c.score,
            "label": c.label,
            "title": (c.property_data or {}).get("title"),
            "price_inr": (c.property_data or {}).get("price_inr"),
            "city": (c.property_data or {}).get("city"),
            "locality": (c.property_data or {}).get("locality"),
            "portal": c.portal,
            "checked_at": c.checked_at.isoformat() if c.checked_at else None,
        }
        for c in matching[:RECENT_CHECKS_PER_BUILDER]
    ]

    return {
        "slug": slug,
        "name": display_name,
        "aliases": [n for n in matching_names if n != display_name],
        "total_checks": len(matching),
        "avg_score": avg_score,
        "label_breakdown": {
            "safe": label_counts.get("safe", 0),
            "caution": label_counts.get("caution", 0),
            "risky": label_counts.get("risky", 0),
        },
        "cities": cities,
        "states": states,
        "rera_records": rera_items,
        "complaints": complaints,
        "recent_checks": recent_checks,
    }
