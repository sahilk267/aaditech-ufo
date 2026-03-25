-- Seed data for development
-- Only runs in development environment

-- Insert sample data if needed
-- This is optional and will be populated via the entrypoint.sh script

INSERT INTO audit_log (event_type, action, outcome, reason)
VALUES ('system.startup', 'initialize', 'success', 'Database initialized successfully')
ON CONFLICT DO NOTHING;
