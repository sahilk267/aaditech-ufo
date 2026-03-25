-- Initial PostgreSQL setup
-- This file runs on the postgres container during initialization

-- Create UUID extension (useful for generating IDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create ltree extension (useful for hierarchical queries)
CREATE EXTENSION IF NOT EXISTS "ltree";

-- Enable log sampling for debugging (can be disabled in production)
ALTER DATABASE aaditech_ufo SET statement_timeout = '30s';
ALTER DATABASE aaditech_ufo SET lock_timeout = '10s';

-- Create a basic audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    actor_id UUID,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    outcome VARCHAR(20),
    reason TEXT,
    request_id VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX ON (timestamp),
    INDEX ON (actor_id),
    INDEX ON (event_type)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
