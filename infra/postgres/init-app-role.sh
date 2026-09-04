#!/usr/bin/env sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER requerido}"
: "${POSTGRES_DB:?POSTGRES_DB requerido}"
: "${HYS_DB_APP_PASSWORD:?HYS_DB_APP_PASSWORD requerido}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=app_user=hys_app \
  --set=app_password="$HYS_DB_APP_PASSWORD" \
  --set=app_database="$POSTGRES_DB" <<'SQL'
SELECT format(
  'CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
  :'app_user',
  :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
\gexec

SELECT format(
  'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS',
  :'app_user',
  :'app_password'
)
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'app_database', :'app_user')
\gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user')
\gexec
SQL
