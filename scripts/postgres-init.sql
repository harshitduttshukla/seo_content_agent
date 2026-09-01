-- Local-only non-owner application role so RLS is exercised during development.
CREATE ROLE seo_content_app LOGIN PASSWORD 'seo_content_app';
GRANT CONNECT ON DATABASE seo_content TO seo_content_app;
GRANT USAGE ON SCHEMA public TO seo_content_app;
