-- PostgreSQL initialization script for EduPulse
-- This runs automatically when the container starts
-- PostgreSQL automatically creates the database specified in POSTGRES_DB env var
-- This script sets up extensions and configuration

-- Create common extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Print confirmation
SELECT 'EduPulse PostgreSQL database initialized successfully' AS status;
