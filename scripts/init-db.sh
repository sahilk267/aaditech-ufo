#!/bin/sh
set -e

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"

psql --set=ON_ERROR_STOP=1 -v db="$POSTGRES_DB" --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "ltree";
ALTER DATABASE :"db" SET statement_timeout = '30s';
ALTER DATABASE :"db" SET lock_timeout = '10s';

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
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor_id ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
EOSQL
