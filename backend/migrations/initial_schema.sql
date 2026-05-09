BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial_schema

CREATE TABLE checks (
    id TEXT NOT NULL, 
    portal TEXT NOT NULL, 
    listing_id TEXT NOT NULL, 
    url TEXT NOT NULL, 
    score INTEGER NOT NULL, 
    label TEXT NOT NULL, 
    summary TEXT NOT NULL, 
    red_flags JSONB DEFAULT '[]'::jsonb NOT NULL, 
    green_flags JSONB DEFAULT '[]'::jsonb NOT NULL, 
    checklist JSONB DEFAULT '[]'::jsonb NOT NULL, 
    verifications JSONB DEFAULT '{}'::jsonb NOT NULL, 
    property_data JSONB DEFAULT '{}'::jsonb NOT NULL, 
    cache_hit BOOLEAN DEFAULT FALSE NOT NULL, 
    source_surface TEXT NOT NULL, 
    requester_ip INET, 
    user_agent TEXT, 
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT checks_score_range CHECK (score BETWEEN 0 AND 100), 
    CONSTRAINT checks_label_enum CHECK (label IN ('safe','caution','risky')), 
    CONSTRAINT checks_source_surface_enum CHECK (source_surface IN ('web','extension','whatsapp','api'))
);

CREATE INDEX idx_checks_portal_listing ON checks (portal, listing_id);

CREATE INDEX idx_checks_checked_at ON checks (checked_at DESC);

CREATE INDEX idx_checks_score ON checks (score);

CREATE TABLE properties (
    id BIGSERIAL NOT NULL, 
    portal TEXT NOT NULL, 
    listing_id TEXT NOT NULL, 
    title TEXT, 
    price_inr BIGINT, 
    bhk SMALLINT, 
    area_sqft INTEGER, 
    locality TEXT, 
    city TEXT, 
    state TEXT, 
    rera_id TEXT, 
    builder_name TEXT, 
    listed_at TIMESTAMP WITH TIME ZONE, 
    images JSONB DEFAULT '[]'::jsonb NOT NULL, 
    raw JSONB, 
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT properties_portal_listing_unique UNIQUE (portal, listing_id)
);

CREATE INDEX idx_properties_locality_bhk ON properties (city, locality, bhk);

CREATE INDEX idx_properties_rera ON properties (rera_id) WHERE rera_id IS NOT NULL;

CREATE INDEX idx_properties_builder ON properties (builder_name) WHERE builder_name IS NOT NULL;

CREATE TABLE images (
    id BIGSERIAL NOT NULL, 
    property_id BIGINT NOT NULL, 
    url TEXT NOT NULL, 
    phash BIGINT NOT NULL, 
    sha256 TEXT, 
    width INTEGER, 
    height INTEGER, 
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(property_id) REFERENCES properties (id) ON DELETE CASCADE
);

CREATE INDEX idx_images_phash ON images (phash);

CREATE TABLE locality_prices (
    id BIGSERIAL NOT NULL, 
    city TEXT NOT NULL, 
    locality TEXT NOT NULL, 
    bhk SMALLINT NOT NULL, 
    avg_price_per_sqft INTEGER NOT NULL, 
    sample_size INTEGER NOT NULL, 
    refreshed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT locality_prices_unique UNIQUE (city, locality, bhk)
);

CREATE TABLE rera_records (
    id BIGSERIAL NOT NULL, 
    state TEXT NOT NULL, 
    rera_id TEXT NOT NULL, 
    project_name TEXT, 
    builder_name TEXT, 
    status TEXT, 
    raw JSONB, 
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT rera_state_rera_unique UNIQUE (state, rera_id)
);

CREATE INDEX idx_rera_builder ON rera_records (builder_name);

CREATE TABLE builder_complaints (
    id BIGSERIAL NOT NULL, 
    builder_name TEXT NOT NULL, 
    state TEXT NOT NULL, 
    open_count INTEGER DEFAULT 0 NOT NULL, 
    closed_count INTEGER DEFAULT 0 NOT NULL, 
    delays_count INTEGER DEFAULT 0 NOT NULL, 
    last_complaint_at TIMESTAMP WITH TIME ZONE, 
    refreshed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT builder_complaints_unique UNIQUE (builder_name, state)
);

CREATE TABLE feedback (
    id BIGSERIAL NOT NULL, 
    check_id TEXT NOT NULL, 
    reason TEXT NOT NULL, 
    note TEXT, 
    reporter_email TEXT, 
    status TEXT DEFAULT 'pending' NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT feedback_status_enum CHECK (status IN ('pending','reviewed','accepted','rejected')), 
    FOREIGN KEY(check_id) REFERENCES checks (id)
);

INSERT INTO alembic_version (version_num) VALUES ('0001_initial_schema') RETURNING alembic_version.version_num;

COMMIT;

