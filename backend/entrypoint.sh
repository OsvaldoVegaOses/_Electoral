#!/bin/sh
set -e

case "${1:-serve}" in
    migrate)
        # Release job with the migrator identity, never a replica startup retry.
        exec alembic upgrade head
        ;;
    serve) ;;
    *) echo "Uso: entrypoint.sh [serve|migrate]" >&2; exit 64 ;;
esac

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
    case "${ENVIRONMENT:-development}" in
        development|test) alembic upgrade head ;;
        *) echo "Migraciones al arranque bloqueadas; ejecute el job de release con identidad separada." >&2; exit 64 ;;
    esac
fi

echo "==> Iniciando servidor de aplicaciones TheoGen Electoral..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
