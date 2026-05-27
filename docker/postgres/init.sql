-- =============================================================
-- DB Copilot — Internal Metadata DB bootstrap
-- Runs on first container startup via /docker-entrypoint-initdb.d/
-- SQLAlchemy creates the actual tables on app startup; this script
-- only ensures the DB and user exist and grants are correct.
-- =============================================================

-- The database and user are created by Docker environment variables:
--   POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD
-- But we set up extensions and permissions here.

-- Enable pg_trgm for future fuzzy search on schema/table names
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable uuid-ossp for potential future UUID primary keys
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant all privileges to the app user (already owner via POSTGRES_USER)
-- This is a no-op if already owner, but kept for explicitness
GRANT ALL PRIVILEGES ON DATABASE dbcopilot_meta TO dbcopilot;

-- Set default search path
ALTER USER dbcopilot SET search_path TO public;

-- Print confirmation
DO $$
BEGIN
    RAISE NOTICE 'DB Copilot metadata database initialized successfully.';
END $$;
