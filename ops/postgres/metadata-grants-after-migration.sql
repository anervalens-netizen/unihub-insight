-- Compatibility check only. Migration 001 grants the metadata authority
-- explicitly on insight.dashboards; no runtime role receives DML on the
-- migration registry or catch-all/default privileges for future tables.
SELECT has_schema_privilege('unihub_insight_metadata', 'insight', 'USAGE')
   AND has_table_privilege('unihub_insight_metadata', 'insight.dashboards', 'SELECT,INSERT,UPDATE,DELETE')
   AND NOT has_table_privilege('unihub_insight_metadata', 'insight.schema_migrations', 'UPDATE')
   AS metadata_authority_is_exact;
