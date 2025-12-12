-- Initialize PostgreSQL database with Apache AGE extension for LightRAG
-- This script runs automatically when the postgres container starts for the first time

-- Step 1: Create the AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Step 2: Load the AGE extension into the current session
LOAD 'age';

-- Step 3: Set the search path to include ag_catalog for graph functions
-- This ensures graph functions are available without schema qualification
SET search_path = ag_catalog, "$user", public;

-- Step 4: Create a function to initialize AGE for each session
-- This is needed because LOAD 'age' only affects the current session
CREATE OR REPLACE FUNCTION public.init_age() RETURNS void AS $$
BEGIN
    LOAD 'age';
    PERFORM set_config('search_path', 'ag_catalog, "$user", public', false);
END;
$$ LANGUAGE plpgsql;

-- Step 5: Grant necessary permissions to the lightrag user
GRANT ALL PRIVILEGES ON DATABASE lightrag TO lightrag;
GRANT USAGE ON SCHEMA ag_catalog TO lightrag;
GRANT ALL ON ALL TABLES IN SCHEMA ag_catalog TO lightrag;
GRANT ALL ON ALL SEQUENCES IN SCHEMA ag_catalog TO lightrag;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA ag_catalog TO lightrag;
GRANT EXECUTE ON FUNCTION public.init_age() TO lightrag;

-- Step 6: Ensure future objects have correct permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA ag_catalog GRANT ALL ON TABLES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA ag_catalog GRANT ALL ON SEQUENCES TO lightrag;
ALTER DEFAULT PRIVILEGES IN SCHEMA ag_catalog GRANT ALL ON FUNCTIONS TO lightrag;

-- Step 7: Create pgcrypto extension for encryption (used for LLM API keys)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Note: LightRAG will automatically create its own tables (kv_storage, vector_storage, 
-- graph_storage, etc.) when it starts up via the check_tables() method in postgres_impl.py
-- No manual table creation needed here.
