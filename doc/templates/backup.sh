#!/usr/bin/env bash
# =============================================================================
# TheoGen Electoral — Script de Respaldo Automatizado de Base de Datos
# =============================================================================
# Uso: ./backup.sh
# Programación recomendada en crontab: 0 */6 * * * /usr/local/bin/theogen-backup.sh
# =============================================================================

set -eo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/theogen}"
CONTAINER_NAME="${DB_CONTAINER:-theogen_db}"
DB_USER="${POSTGRES_USER:-theogen}"
DB_NAME="${POSTGRES_DB:-theogen_electoral}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/theogen_${DB_NAME}_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"

# 1. Crear directorio de respaldos si no existe
mkdir -p "${BACKUP_DIR}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] INICIO: Respaldo de la base de datos '${DB_NAME}'..."

# 2. Verificar que el contenedor de base de datos esté corriendo
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ERROR: El contenedor '${CONTAINER_NAME}' no está en ejecución." >&2
    exit 1
fi

# 3. Ejecutar pg_dump y comprimir con gzip nivel 9
docker exec -t "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --no-owner --clean --if-exists | gzip -9 > "${BACKUP_FILE}"

# 4. Validar que el archivo de respaldo exista y no esté vacío
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ERROR: El archivo de respaldo se creó vacío o falló la extracción." >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# 5. Generar Checksum SHA-256 para verificación de integridad
sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] ÉXITO: Respaldo completado (${FILESIZE}): ${BACKUP_FILE}"
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Checksum SHA-256: $(cat "${CHECKSUM_FILE}")"

# 6. Rotación: Eliminar respaldos más antiguos que RETENTION_DAYS
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Limpiando respaldos con más de ${RETENTION_DAYS} días de antigüedad..."
find "${BACKUP_DIR}" -name "theogen_${DB_NAME}_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}" -name "theogen_${DB_NAME}_*.sha256" -mtime "+${RETENTION_DAYS}" -delete

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Proceso de respaldo finalizado exitosamente."
