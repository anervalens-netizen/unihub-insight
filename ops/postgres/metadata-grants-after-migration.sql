GRANT USAGE ON SCHEMA insight TO unihub_insight_metadata;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA insight
    TO unihub_insight_metadata;
ALTER DEFAULT PRIVILEGES FOR ROLE unihub_insight_migrator IN SCHEMA insight
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO unihub_insight_metadata;
