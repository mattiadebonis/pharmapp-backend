#!/usr/bin/env bash
# Postgres docker-entrypoint scans only the top level of
# /docker-entrypoint-initdb.d. We want auth.users + roles to apply
# before the application migrations, so this script runs the bootstrap
# SQL first, then iterates the migrations/ volume in lexical order.

set -euo pipefail

BOOTSTRAP_DIR=/docker-entrypoint-initdb.d/auth-bootstrap
MIGRATIONS_DIR=/docker-entrypoint-initdb.d/app-migrations

run_sql() {
    local file="$1"
    echo ">> applying $(basename "$file")"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$file"
}

if [ -d "$BOOTSTRAP_DIR" ]; then
    for f in "$BOOTSTRAP_DIR"/*.sql; do
        [ -f "$f" ] && run_sql "$f"
    done
fi

if [ -d "$MIGRATIONS_DIR" ]; then
    for f in "$MIGRATIONS_DIR"/*.sql; do
        [ -f "$f" ] && run_sql "$f"
    done
fi

# Re-grant service_role privileges that the migrations REVOKEd. Real
# Supabase deploys handle this via default ACLs; the test stack must
# restore it explicitly so PostgREST can serve every table.
echo ">> restoring service_role grants"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "SELECT auth._grant_service_role_all();"
