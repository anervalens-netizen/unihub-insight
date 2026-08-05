BEGIN;

ALTER TABLE insight.dashboards
    ADD COLUMN IF NOT EXISTS query_contract_version INTEGER NOT NULL DEFAULT 1
        CHECK (query_contract_version >= 1),
    ADD COLUMN IF NOT EXISTS scope_ceiling JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(scope_ceiling) = 'object');

CREATE TABLE IF NOT EXISTS insight.dashboard_acl (
    dashboard_id TEXT NOT NULL REFERENCES insight.dashboards(id) ON DELETE CASCADE,
    subject TEXT NOT NULL CHECK (char_length(subject) BETWEEN 1 AND 256),
    permission TEXT NOT NULL CHECK (permission IN ('read', 'edit', 'admin')),
    granted_by_subject TEXT NOT NULL CHECK (char_length(granted_by_subject) BETWEEN 1 AND 256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dashboard_id, subject)
);

CREATE INDEX IF NOT EXISTS dashboard_acl_subject_idx
    ON insight.dashboard_acl (subject, dashboard_id);

CREATE TABLE IF NOT EXISTS insight.dashboard_versions (
    dashboard_id TEXT NOT NULL REFERENCES insight.dashboards(id) ON DELETE CASCADE,
    version INTEGER NOT NULL CHECK (version >= 1),
    document JSONB NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    actor_subject TEXT NOT NULL CHECK (char_length(actor_subject) BETWEEN 1 AND 256),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dashboard_id, version)
);

CREATE TABLE IF NOT EXISTS insight.filter_presets (
    id TEXT PRIMARY KEY,
    owner_subject TEXT NOT NULL CHECK (char_length(owner_subject) BETWEEN 1 AND 256),
    name TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
    filters JSONB NOT NULL CHECK (jsonb_typeof(filters) = 'object'),
    shared BOOLEAN NOT NULL DEFAULT false,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS filter_presets_owner_updated_idx
    ON insight.filter_presets (owner_subject, updated_at DESC);

CREATE TABLE IF NOT EXISTS insight.user_directory (
    subject TEXT PRIMARY KEY CHECK (char_length(subject) BETWEEN 1 AND 256),
    email TEXT,
    display_name TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS insight.query_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_subject TEXT NOT NULL CHECK (char_length(actor_subject) BETWEEN 1 AND 256),
    action TEXT NOT NULL CHECK (action IN ('inspect', 'export.csv')),
    dashboard_id TEXT REFERENCES insight.dashboards(id) ON DELETE SET NULL,
    widget_id TEXT NOT NULL CHECK (char_length(widget_id) BETWEEN 1 AND 100),
    analytical_snapshot_id TEXT NOT NULL,
    metric_id TEXT NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS query_audit_actor_created_idx
    ON insight.query_audit (actor_subject, created_at DESC);

COMMENT ON TABLE insight.dashboard_acl IS
    'Targeted metadata sharing only; data capability and scope ceilings are rechecked per execution.';
COMMENT ON TABLE insight.dashboard_versions IS
    'Immutable dashboard definition history; analytical result data is never persisted here.';
COMMENT ON TABLE insight.user_directory IS
    'Minimal directory of users already admitted by the external Authentik application boundary.';
COMMENT ON TABLE insight.query_audit IS
    'Append-only actor/time evidence for bounded server-side inspect and CSV export executions.';

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    insight.dashboard_acl,
    insight.filter_presets,
    insight.user_directory
TO unihub_insight_metadata;
GRANT SELECT, INSERT ON TABLE insight.dashboard_versions
TO unihub_insight_metadata;
GRANT INSERT ON TABLE insight.query_audit
TO unihub_insight_metadata;
GRANT USAGE ON SEQUENCE insight.query_audit_id_seq
TO unihub_insight_metadata;

COMMIT;
