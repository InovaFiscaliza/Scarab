#!/bin/sh

set -eu

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${SCARAB_DB_PASSWORD:?SCARAB_DB_PASSWORD is required}"

if [ "$POSTGRES_USER" = "scarab_app" ]; then
    echo "ERROR: POSTGRES_USER must be distinct from scarab_app." >&2
    exit 1
fi

psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --set=ON_ERROR_STOP=1 \
    --set=database_name="$POSTGRES_DB" \
    --set=app_password="$SCARAB_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE scarab_app LOGIN PASSWORD %L', :'app_password')
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'scarab_app')
\gexec
SELECT format('ALTER ROLE scarab_app LOGIN PASSWORD %L', :'app_password')
\gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO scarab_app', :'database_name')
\gexec
GRANT USAGE ON SCHEMA public TO scarab_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON clientes_docs TO scarab_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON carga_historico TO scarab_app;
GRANT USAGE, SELECT ON SEQUENCE carga_historico_id_seq TO scarab_app;
GRANT EXECUTE ON FUNCTION processar_operacao_json(TEXT, JSONB) TO scarab_app;
REVOKE CREATE ON SCHEMA public FROM scarab_app;
SQL