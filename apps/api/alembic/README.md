# Alembic migrations

`versions/` is intentionally empty in Phase 0 because no product schema has been implemented. The environment is wired to the dedicated synchronous `DATABASE_MIGRATION_URL` and shared SQLAlchemy metadata. Phase 1 must import the complete model registry through `app.models` before autogeneration and create an explicit reviewed baseline revision. Do not autogenerate an empty or fictional schema.
