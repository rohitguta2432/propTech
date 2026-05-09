# Database Schema (Postgres)

Source of truth for all table definitions. Update this spec in the same PR as any migration.

Hosted on Supabase. Connection via standard Postgres URL.

---

## Tables

### `checks`
Every user-submitted check. The primary user-facing record.

```sql
CREATE TABLE checks (
    id              TEXT PRIMARY KEY,                  -- e.g. "chk_a3f2..."
    portal          TEXT NOT NULL,                     -- 'magicbricks' | '99acres' | 'housing' | 'nobroker'
    listing_id      TEXT NOT NULL,                     -- portal's listing ID
    url             TEXT NOT NULL,
    score           INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    label           TEXT NOT NULL CHECK (label IN ('safe','caution','risky')),
    summary         TEXT NOT NULL,
    red_flags       JSONB NOT NULL DEFAULT '[]'::jsonb,
    green_flags     JSONB NOT NULL DEFAULT '[]'::jsonb,
    checklist       JSONB NOT NULL DEFAULT '[]'::jsonb,
    verifications   JSONB NOT NULL DEFAULT '{}'::jsonb,
    property_data   JSONB NOT NULL DEFAULT '{}'::jsonb,
    cache_hit       BOOLEAN NOT NULL DEFAULT FALSE,
    source_surface  TEXT NOT NULL CHECK (source_surface IN ('web','extension','whatsapp','api')),
    requester_ip    INET,
    user_agent      TEXT,
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_checks_portal_listing ON checks (portal, listing_id);
CREATE INDEX idx_checks_checked_at     ON checks (checked_at DESC);
CREATE INDEX idx_checks_score          ON checks (score);
```

### `properties`
Normalized listing snapshots. One row per (portal, listing_id) — used for duplicate detection across portals.

```sql
CREATE TABLE properties (
    id              BIGSERIAL PRIMARY KEY,
    portal          TEXT NOT NULL,
    listing_id      TEXT NOT NULL,
    title           TEXT,
    price_inr       BIGINT,
    bhk             SMALLINT,
    area_sqft       INTEGER,
    locality        TEXT,
    city            TEXT,
    state           TEXT,
    rera_id         TEXT,
    builder_name    TEXT,
    listed_at       TIMESTAMPTZ,                       -- portal's first-seen date
    images          JSONB NOT NULL DEFAULT '[]'::jsonb, -- array of {url, phash}
    raw             JSONB,                              -- full parsed listing
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (portal, listing_id)
);

CREATE INDEX idx_properties_locality_bhk ON properties (city, locality, bhk);
CREATE INDEX idx_properties_rera         ON properties (rera_id) WHERE rera_id IS NOT NULL;
CREATE INDEX idx_properties_builder      ON properties (builder_name) WHERE builder_name IS NOT NULL;
```

### `images`
Perceptual hashes for duplicate / stolen-photo detection across listings.

```sql
CREATE TABLE images (
    id              BIGSERIAL PRIMARY KEY,
    property_id     BIGINT NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    phash           BIGINT NOT NULL,                   -- 64-bit perceptual hash
    sha256          TEXT,
    width           INTEGER,
    height          INTEGER,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_images_phash ON images (phash);
```

### `locality_prices`
Cached price benchmarks. Refreshed monthly.

```sql
CREATE TABLE locality_prices (
    id              BIGSERIAL PRIMARY KEY,
    city            TEXT NOT NULL,
    locality        TEXT NOT NULL,
    bhk             SMALLINT NOT NULL,
    avg_price_per_sqft   INTEGER NOT NULL,
    sample_size     INTEGER NOT NULL,
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (city, locality, bhk)
);
```

### `rera_records`
Cached Karnataka RERA project data. Refreshed weekly per project.

```sql
CREATE TABLE rera_records (
    id              BIGSERIAL PRIMARY KEY,
    state           TEXT NOT NULL,                     -- 'karnataka' at launch
    rera_id         TEXT NOT NULL,                     -- e.g. 'PRM/KA/RERA/...'
    project_name    TEXT,
    builder_name    TEXT,
    status          TEXT,                              -- 'registered' | 'expired' | 'cancelled'
    raw             JSONB,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (state, rera_id)
);

CREATE INDEX idx_rera_builder ON rera_records (builder_name);
```

### `builder_complaints`
Aggregated complaint count per builder.

```sql
CREATE TABLE builder_complaints (
    id              BIGSERIAL PRIMARY KEY,
    builder_name    TEXT NOT NULL,
    state           TEXT NOT NULL,
    open_count      INTEGER NOT NULL DEFAULT 0,
    closed_count    INTEGER NOT NULL DEFAULT 0,
    delays_count    INTEGER NOT NULL DEFAULT 0,
    last_complaint_at TIMESTAMPTZ,
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (builder_name, state)
);
```

### `feedback`
User-flagged wrong scores. Manual review queue.

```sql
CREATE TABLE feedback (
    id              BIGSERIAL PRIMARY KEY,
    check_id        TEXT NOT NULL REFERENCES checks(id),
    reason          TEXT NOT NULL,
    note            TEXT,
    reporter_email  TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','reviewed','accepted','rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at     TIMESTAMPTZ
);
```

---

## Migration approach

- Use **Alembic** (Python's standard SQL migration tool, integrates with SQLAlchemy).
- One migration per PR. Never edit a merged migration; always create a new one.
- Migrations live in `backend/migrations/versions/`.
- Naming: `2026_05_09_001_create_checks_table.py`.
- Forward + rollback both required.

---

## What we don't store at MVP

- Personal user data (no accounts).
- Phone numbers or names from WhatsApp users.
- Original listing HTML in DB (use R2 for screenshots only, with TTL).
- Anything that could violate portal ToS (we display, never republish).

---

## Retention

| Data | Retention |
|---|---|
| `checks` | 12 months (then archive to cold storage) |
| `properties` | Indefinite (it's the moat) |
| `images` | Indefinite |
| `locality_prices` | Last 24 months |
| `rera_records` | Indefinite |
| `feedback` | Indefinite |
| Server logs | 30 days |
