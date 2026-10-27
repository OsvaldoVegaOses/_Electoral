# 04. Respaldos y Recuperación ante Desastres (Disaster Recovery)
### TheoGen Electoral — Participación transparente y verificable

La integridad y disponibilidad de la información electoral exige una política de respaldos (*backups*) rigurosa, automatizada y probada periódicamente. Durante un proceso de votación, la pérdida de un solo voto o acta es inadmisible.

---

## 🎯 1. Objetivos del Plan de Recuperación

| Métrica | Objetivo Estándar | Objetivo durante Día de Elección |
|---|---|---|
| **RTO (Recovery Time Objective)** | < 30 minutos | **< 10 minutos** para restaurar el servicio en caso de fallo crítico. |
| **RPO (Recovery Point Objective)** | < 6 horas | **< 15 minutos** (o 0 con replicación continua de WALs). |

---

## 💾 2. Qué Componentes Deben Respaldarse

1. **Base de Datos PostgreSQL (Prioridad Crítica):**
   - Tablas de padrón (`voters`), elecciones (`elections`), candidatos (`candidates`), votos emitidos (`votes`) y bitácora de auditoría (`audit_logs`).
2. **Secretos de Cifrado y Entorno:**
   - Archivo `.env` (contiene `SECRET_KEY`, `VOTE_HMAC_KEY`, `POSTGRES_PASSWORD`).
   - *Nota:* Debe almacenarse cifrado con clave PGP / GPG o en un gestor de secretos (Bitwarden, AWS Secrets Manager, HashiCorp Vault).
3. **Certificados SSL y Configuración:**
   - Certificados Let's Encrypt (`/etc/letsencrypt/`) y configuración de Nginx.

---

## ⚙️ 3. Automatización de Respaldos con Script y Cron

El repositorio incluye el script [`doc/templates/backup.sh`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/backup.sh), el cual ejecuta `pg_dump` dentro del contenedor Docker de base de datos, comprime el resultado con `gzip`, verifica la integridad del archivo y elimina copias con más de 30 días de antigüedad.

### 3.1. Instalación del Script en el Servidor
```bash
# 1. Crear directorio para almacenar los respaldos
sudo mkdir -p /var/backups/theogen
sudo chown -R theogen:theogen /var/backups/theogen
sudo chmod 700 /var/backups/theogen

# 2. Copiar script de respaldo a una ubicación ejecutable
sudo cp /opt/theogen-electoral/doc/templates/backup.sh /usr/local/bin/theogen-backup.sh
sudo chmod +x /usr/local/bin/theogen-backup.sh

# 3. Probar ejecución manual
/usr/local/bin/theogen-backup.sh
```

### 3.2. Programación en Crontab

Abra el editor de cron para el usuario `theogen`:
```bash
crontab -e
```

Agregue las siguientes líneas de programación:

```cron
# Respaldo automático cada 6 horas en días normales
0 */6 * * * /usr/local/bin/theogen-backup.sh >> /var/log/theogen-backup.log 2>&1

# Sincronización externa diaria hacia almacenamiento en la nube (ej. AWS S3 / Cloudflare R2) a las 03:00 AM
0 3 * * * rclone sync /var/backups/theogen remote-s3:theogen-electoral-backups/ --checksum >> /var/log/theogen-sync.log 2>&1
```

> [!TIP]
> **Modo Día de Elección:** Durante las 8 a 12 horas en que las mesas receptoras de sufragios estén abiertas, se recomienda intensificar la frecuencia de respaldo a **cada 15 minutos**:
> ```cron
> */15 * * * * /usr/local/bin/theogen-backup.sh >> /var/log/theogen-backup.log 2>&1
> ```

---

## ☁️ 4. Almacenamiento Fuera de Sitio (Offsite Storage)

Para cumplir con la regla de respaldo **3-2-1** (3 copias de los datos, en 2 soportes distintos, 1 de ellos fuera del centro de datos):
- Los respaldos locales en `/var/backups/theogen` deben sincronizarse automáticamente hacia un proveedor cloud independiente (ej. AWS S3, Cloudflare R2, Wasabi o Backblaze B2).
- Herramienta recomendada: `rclone` con cifrado en tránsito y en reposo (`crypt`).

---

## 🔄 5. Procedimiento de Restauración Paso a Paso

Si ocurre una falla catastrófica, corrupción de datos o es necesario recuperar el estado previo a un incidente, siga estos pasos:

### Paso 1: Identificar el archivo de respaldo a restaurar
```bash
ls -lh /var/backups/theogen/
# Ejemplo: theogen_backup_20261027_140000.sql.gz
```

### Paso 2: Detener temporalmente el backend para evitar escrituras concurrentes
```bash
cd /opt/theogen-electoral
docker compose -f docker-compose.prod.yml stop backend
```

### Paso 3: Ejecutar la restauración usando el script oficial
```bash
# Ejecutar script de restauración
/opt/theogen-electoral/doc/templates/restore.sh /var/backups/theogen/theogen_backup_20261027_140000.sql.gz
```

### Paso 4: Reactivar el backend y verificar la integridad
```bash
docker compose -f docker-compose.prod.yml start backend

# Verificar salud del sistema
curl -f http://127.0.0.1:8000/api/health

# Consultar bitácora de auditoría para verificar última transacción
docker compose -f docker-compose.prod.yml exec -T db psql -U theogen -d theogen_electoral -c "SELECT id, accion, created_at FROM audit_logs ORDER BY id DESC LIMIT 5;"
```

---

## 🗳️ 6. Protocolo Operativo para el "Día de la Elección" (Día D)

### 6.1. Antes de Iniciar la Votación (T - 2 horas)
- [ ] Ejecutar comprobación de salud del servidor (`htop`, espacio en disco `df -h`).
- [ ] Comprobar que el firewall UFW esté activo y el certificado SSL tenga más de 30 días de vigencia.
- [ ] Tomar un **Snapshot / Backup inicial en frío** del servidor completo.
- [ ] Verificar que la urna esté en cero (`votos = 0`) y descargar el **Acta de Apertura (PDF)** firmada por la comisión.
- [ ] Activar el cron de respaldo cada 15 minutos.

### 6.2. Durante la Jornada de Votación
- [ ] Monitorear el consumo de CPU/RAM y tasa de votos por minuto en el Dashboard.
- [ ] **Congelamiento de Código (Code Freeze):** Queda estrictamente prohibido aplicar despliegues, parches o cambios de configuración en el servidor durante el horario de votación.
- [ ] Canal de comunicación prioritario abierto con el equipo técnico y la comisión electoral.

### 6.3. Al Cierre de la Elección
- [ ] Cerrar formalmente el proceso en el panel administrativo.
- [ ] Generar y descargar el **Acta de Cierre y Escrutinio Definitivo (PDF)**.
- [ ] Ejecutar un respaldo definitivo e inmediato etiquetado como `CIERRE_OFICIAL_<ELECCION_ID>_<FECHA>.sql.gz`.
- [ ] Almacenar una copia firmada digitalmente del acta y del dump en almacenamiento inmutable (WORM / Object Lock).
