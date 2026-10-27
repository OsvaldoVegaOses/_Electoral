#!/usr/bin/env bash
# =============================================================================
# TheoGen Electoral — Script de Restauración de Base de Datos
# =============================================================================
# Uso: ./restore.sh /ruta/al/archivo_backup.sql.gz
# =============================================================================

set -eo pipefail

if [ -z "$1" ]; then
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
    sha256sum -c "${CHECKSUM_FILE}"
    echo "--> Checksum válido."
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
read -p "¿Está seguro de proceder con la restauración? (escriba 'SI' en mayúsculas): " CONFIRMATION

if [ "${CONFIRMATION}" != "SI" ]; then
    echo "Operación cancelada por el usuario."
    exit 0
fi

# 2. Desconectar clientes activos antes de restaurar
echo "--> Terminando conexiones activas a la base de datos '${DB_NAME}'..."
docker exec -t "${CONTAINER_NAME}" psql -U "${DB_USER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" || true

# 3. Restaurar flujo según el tipo de compresión
echo "--> Restaurando dump en '${DB_NAME}'..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1
else
    cat "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1
fi

echo "======================================================================"
echo "✅ RESTAURACIÓN COMPLETADA EXITOSAMENTE"
echo "======================================================================"
echo "Verificando recuento de tablas..."
docker exec -t "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT 'Elecciones' as entidad, count(*) as total FROM elections UNION ALL SELECT 'Electores', count(*) FROM voters UNION ALL SELECT 'Votos Emitidos', count(*) FROM votes;"
