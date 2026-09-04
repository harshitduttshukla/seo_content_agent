-- Local-only non-owner application role so RLS is exercised during development.
CREATE ROLE seo_content_app LOGIN PASSWORD 'seo_content_app';
GRANT CONNECT ON DATABASE seo_content TO seo_content_app;
GRANT USAGE, CREATE ON SCHEMA public TO seo_content_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO seo_content_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO seo_content_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO seo_content_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO seo_content_app;

