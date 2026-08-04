BEGIN;

CREATE SCHEMA IF NOT EXISTS insight;

CREATE TABLE IF NOT EXISTS insight.schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS insight.dashboards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
    description TEXT NOT NULL DEFAULT '' CHECK (char_length(description) <= 600),
    owner_subject TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private'
        CHECK (visibility IN ('private', 'shared')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    widgets JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(widgets) = 'array'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS dashboards_owner_updated_idx
    ON insight.dashboards (owner_subject, updated_at DESC);
CREATE INDEX IF NOT EXISTS dashboards_shared_updated_idx
    ON insight.dashboards (updated_at DESC)
    WHERE visibility = 'shared';

COMMENT ON SCHEMA insight IS 'UniHub Insight-owned metadata only; Retail business data remains read-only.';
COMMENT ON TABLE insight.dashboards IS 'Versioned dashboard definitions without embedded analytical result snapshots.';

COMMIT;
