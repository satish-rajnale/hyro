#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v app_db="$APP_DB_NAME" -v temporal_db="$TEMPORAL_DB_NAME" -v visibility_db="$TEMPORAL_VISIBILITY_DB_NAME" <<'SQL'
SELECT format('CREATE DATABASE %I', :'app_db') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'app_db') \gexec
SELECT format('CREATE DATABASE %I', :'temporal_db') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'temporal_db') \gexec
SELECT format('CREATE DATABASE %I', :'visibility_db') WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'visibility_db') \gexec
SQL
