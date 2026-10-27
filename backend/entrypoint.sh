#!/bin/sh
set -e

echo "==> Verificando y aplicando migraciones de base de datos Alembic..."
alembic upgrade head

echo "==> Iniciando servidor de aplicaciones TheoGen Electoral..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
