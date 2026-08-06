BEGIN;

ALTER TABLE insight.query_audit
    DROP CONSTRAINT IF EXISTS query_audit_action_check;

ALTER TABLE insight.query_audit
    ADD CONSTRAINT query_audit_action_check
    CHECK (
        action IN (
            'inspect',
            'export.csv',
            'export.xlsx',
            'export.overview.xlsx',
            'export.module.xlsx',
            'export.monthly.xlsx'
        )
    );

COMMENT ON TABLE insight.query_audit IS
    'Append-only actor/time evidence for bounded server-side inspect and tabular widget exports.';

COMMIT;
