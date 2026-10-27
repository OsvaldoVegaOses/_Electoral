#!/usr/bin/env bash
# =============================================================================
# TheoGen Electoral — Script de Restauración de Base de Datos
# =============================================================================
# Uso: ./restore.sh /ruta/al/archivo_backup.sql.gz
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Uso: $0 <archivo_de_respaldo.sql.gz>"
    echo "Ejemplo: $0 /var/backups/theogen/theogen_theogen_electoral_20261027_140000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
CONTAINER_NAME="${DB_CONTAINER:-theogen_db}"
DB_USER="${POSTGRES_USER:-theogen}"
DB_NAME="${POSTGRES_DB:-theogen_electoral}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "ERROR: El archivo de respaldo '${BACKUP_FILE}' no existe." >&2
    exit 1
fi

# 1. Comprobación de Checksum si existe archivo .sha256 adyacente
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    echo "--> Validando Checksum SHA-256..."
    # sha256sum -c requiere ejecutarse desde el directorio del backup
    (cd "$(dirname "${BACKUP_FILE}")" && sha256sum -c "${CHECKSUM_FILE}")
    echo "--> Checksum válido."
else
    echo "AVISO: No se encontró archivo de checksum '${CHECKSUM_FILE}'. Continuando sin verificación de integridad." >&2
fi

echo "======================================================================"
echo "⚠️  ADVERTENCIA CRÍTICA DE RESTAURACIÓN"
echo "======================================================================"
echo "Base de datos destino: ${DB_NAME}"
echo "Contenedor:            ${CONTAINER_NAME}"
echo "Archivo origen:        ${BACKUP_FILE}"
echo ""
echo "Esta acción SOBREESCRIBIRÁ los datos actuales de la base de datos."
echo "======================================================================"

# Guardia para entornos no-interactivos (cron, CI): requiere variable CONFIRM_RESTORE=SI
if [ -t 0 ]; then
    # Terminal interactiva: pedir confirmación al usuario
    read -r -p "¿Está seguro de proceder con la restauración? (escriba 'SI' en mayúsculas): " CONFIRMATION
else
    # No-interactivo: usar variable de entorno
    CONFIRMATION="${CONFIRM_RESTORE:-NO}"
    echo "Modo no-interactivo. CONFIRM_RESTORE='${CONFIRMATION}'"
fi

if [ "${CONFIRMATION}" != "SI" ]; then
    echo "Operación cancelada."
    exit 0
fi

# 2. Desconectar clientes activos antes de restaurar
echo "--> Terminando conexiones activas a la base de datos '${DB_NAME}'..."
# NOTA: Se usa -i en lugar de -t para evitar caracteres de control en salida
docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" || true

# 3. Restaurar flujo según el tipo de compresión
echo "--> Restaurando dump en '${DB_NAME}'..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1
else
    docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 < "${BACKUP_FILE}"
fi

echo "======================================================================"
echo "✅ RESTAURACIÓN COMPLETADA EXITOSAMENTE"
echo "======================================================================"
echo "Verificando recuento de tablas..."
docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT 'Elecciones' as entidad, count(*) as total FROM elections UNION ALL SELECT 'Electores', count(*) FROM voters UNION ALL SELECT 'Votos Emitidos', count(*) FROM votes;"
