SELECT 'CREATE DATABASE ttrpg_auth'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'ttrpg_auth'
)
\gexec

GRANT ALL PRIVILEGES ON DATABASE ttrpg_auth TO ttrpg;
