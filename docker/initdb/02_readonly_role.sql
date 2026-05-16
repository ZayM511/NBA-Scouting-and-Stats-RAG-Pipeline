-- 02_readonly_role.sql — create the read-only role used by the postgres MCP
-- server and any other tool that needs query access without write privileges.
--
-- Runs once when the Postgres container is first initialized.
-- Defense-in-depth alongside the sql-reviewer agent.

CREATE ROLE nbarag_readonly WITH LOGIN PASSWORD 'nbarag_readonly';

GRANT CONNECT ON DATABASE nbarag TO nbarag_readonly;
GRANT USAGE ON SCHEMA public TO nbarag_readonly;

-- SELECT on every existing table.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nbarag_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO nbarag_readonly;

-- SELECT on every future table created by the migration user.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO nbarag_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO nbarag_readonly;

-- Explicitly deny anything else. The default for a freshly created role is
-- already deny, but writing it out makes the intent obvious to future readers.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public
    FROM nbarag_readonly;
