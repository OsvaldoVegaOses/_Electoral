# 05. Monitoreo, Operaciones y Mantenimiento
### TheoGen Electoral — Participación transparente y verificable

Este documento describe los procedimientos de monitoreo en tiempo real, gestión de bitácoras (*logging*), mantenimiento periódico y diagnóstico de incidencias para asegurar la máxima estabilidad operacional de **TheoGen Electoral**.

---

## 💓 1. Endpoints de Verificación de Salud (Health Checks)

La plataforma cuenta con endpoints ligeros para comprobaciones sintéticas automáticas:

### 1.1. Healthcheck del Backend
- **Endpoint:** `GET /api/health`
- **Respuesta esperada (HTTP 200 OK):**
  ```json
  {
    "status": "ok",
    "timestamp": "2026-10-27T10:48:31.000000+00:00"
  }
  ```
- **Uso:** Utilizado por balanceadores de carga, monitores externos (Uptime Kuma, Pingdom, Datadog) y el propio Docker para saber si la API responde correctamente.

### 1.2. Healthcheck de PostgreSQL (Docker)
En `docker-compose.prod.yml`, la base de datos se comprueba activamente cada 5 segundos:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 5s
  timeout: 5s
  retries: 5
```
El contenedor `backend` solo inicia cuando el servicio `db` alcanza el estado `healthy`, evitando errores de conexión al arranque.

---

## 📊 2. Monitoreo de Recursos en Tiempo Real

### 2.1. Inspección Rápida por Terminal
Para monitorear el consumo de CPU, RAM y red de los contenedores en tiempo real:

```bash
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
```

Salida típica esperada:
```
NAME               CPU %     MEM USAGE / LIMIT     NET I/O           BLOCK I/O
theogen_nginx      0.05%     18.2MiB / 3.8GiB      245kB / 1.2MB     0B / 0B
theogen_frontend   0.02%     12.4MiB / 3.8GiB      112kB / 540kB     0B / 0B
theogen_backend    0.45%     185.6MiB / 3.8GiB     2.4MB / 1.8MB     12MB / 4MB
theogen_db         0.12%     210.3MiB / 3.8GiB     1.8MB / 2.4MB     45MB / 80MB
```

### 2.2. Monitoreo Externo Recomendado
Configure una herramienta de uptime externa para alertar inmediatamente al equipo por WhatsApp, Telegram o Correo:
- **Uptime Kuma** (Auto-hospedado en servidor independiente).
- **Better Stack / Better Uptime** o **UptimeRobot** (Gratuito / Cloud).
- **Parámetros:** Probar cada 30 segundos `https://votaciones.theogen.cl/api/health`. Alerta si no responde en 3 segundos o devuelve código distinto a 200.

---

## 📜 3. Gestión de Registros y Bitácoras (Logging)

### 3.1. Visualización de Logs en Vivo
```bash
# Ver todos los logs en tiempo real
docker compose -f docker-compose.prod.yml logs -f --tail 100

# Ver solo logs del backend (FastAPI)
docker compose -f docker-compose.prod.yml logs -f backend --tail 200

# Ver solo accesos y errores del proxy Nginx
docker compose -f docker-compose.prod.yml logs -f nginx --tail 100
```

### 3.2. Rotación de Logs de Docker
Para evitar que los archivos JSON de logs llenen el disco duro, `docker-compose.prod.yml` define:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "5"
```
Esto garantiza que ningún contenedor acumule más de 50 MB de registros en disco.

### 3.3. Bitácora de Auditoría Electoral (Almacenamiento Append-Only y Encadenamiento Criptográfico)
La plataforma no asume que una tabla SQL convencional sea "inmutable" por sí sola. Para garantizar integridad y evidencia verificable de no alteración, **TheoGen Electoral** implementa un modelo de tres capas (P15):
1. **Encadenamiento Criptográfico (Hash Chaining SHA-256)**: Cada registro almacena `prev_hash` (apuntando al registro anterior) y `record_hash` (digest del registro actual). Cualquier mutación o supresión rompe la cadena.
2. **Restricción de Motor (PostgreSQL Append-Only Trigger)**: Un disparador en base de datos (`trg_audit_logs_append_only`) bloquea operaciones `UPDATE` y `DELETE` directas sobre `audit_logs`.
3. **Anclaje Externo (Checkpoints)**: Generación periódica de snapshots criptográficos exportables a almacenamiento WORM o servidores de sellado de tiempo (RFC 3161 TSA).

#### Consulta de registros y eslabones de la cadena:
```bash
docker compose -f docker-compose.prod.yml exec db psql -U theogen -d theogen_electoral -c \
  "SELECT id, fecha, usuario, accion, LEFT(prev_hash, 12) AS prev, LEFT(record_hash, 12) AS hash FROM audit_logs ORDER BY id DESC LIMIT 20;"
```

#### Verificación de integridad de la bitácora:
Para verificar que ningún registro haya sido alterado o eliminado:
```bash
# Vía API (requiere token de Administrador General)
curl -s -X GET "https://votaciones.tucolegio.cl/api/audit/verify-integrity" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```
Respuesta esperada: `{"integro": true, "total_revisados": N, ...}`.

#### Generación de punto de anclaje (Checkpoint):
Al finalizar una jornada electoral o mensualmente, se recomienda generar un anclaje firmado:
```bash
curl -s -X POST "https://votaciones.tucolegio.cl/api/audit/checkpoint" \
  -H "Authorization: Bearer <TOKEN_ADMIN>"
```
El `checkpoint_hash` resultante debe registrarse en el libro de actas físico o archivarse en repositorio independiente fuera del servidor de base de datos.

---

## 🧹 4. Mantenimiento Preventivo Periódico

Ejecute mensualmente o tras jornadas electorales:

```bash
# 1. Comprobar espacio en disco disponible
df -h /

# 2. Eliminar imágenes Docker antiguas o intermedias sin usar
docker image prune -af

# 3. Eliminar volúmenes huérfanos no asociados
docker volume prune -f

# 4. Verificar estado de renovación de certificados SSL
sudo certbot renew --dry-run
```

---

## 🚨 5. Guía de Solución de Problemas (Troubleshooting)

### Problema 1: El Backend no arranca (`RuntimeError: SECRET_KEY no configurada`)
- **Causa:** En modo `ENVIRONMENT=production`, la aplicación exige obligatoriamente claves en `.env` para prevenir vulnerabilidades de seguridad.
- **Solución:**
  1. Revise el archivo `.env`.
  2. Genere las claves:
     ```bash
     python3 -c "import secrets; print(secrets.token_hex(64))"
     ```
  3. Asígnelas a `SECRET_KEY` y `VOTE_HMAC_KEY`.
  4. Reinicie con `docker compose -f docker-compose.prod.yml restart backend`.

---

### Problema 2: Error `502 Bad Gateway` en Nginx
- **Causa:** El proxy reverso Nginx no puede comunicarse con el puerto interno 8000 del backend o el backend se detuvo.
- **Diagnóstico:**
  ```bash
  docker compose -f docker-compose.prod.yml ps
  docker compose -f docker-compose.prod.yml logs backend --tail 50
  ```
- **Solución:** Si el backend está caído por un fallo no controlado, reinicie el contenedor:
  ```bash
  docker compose -f docker-compose.prod.yml restart backend
  ```

---

### Problema 3: Error de conexión con la Base de Datos (`psycopg2.OperationalError`)
- **Causa:** El contenedor `theogen_db` no está listo o la contraseña en `DATABASE_URL` no coincide con `POSTGRES_PASSWORD`.
- **Solución:**
  1. Verifique que ambos valores en `.env` sean idénticos:
     `POSTGRES_PASSWORD=miClave`
     `DATABASE_URL=postgresql://theogen:miClave@db:5432/theogen_electoral`
  2. Verifique que el contenedor `db` esté en estado `healthy`:
     ```bash
     docker inspect --format='{{json .State.Health.Status}}' theogen_db
     ```

---

### Problema 4: Elector indica que su token dice "Token inválido o ya utilizado"
- **Diagnóstico:**
  Consulte el estado del elector en base de datos:
  ```bash
  docker compose -f docker-compose.prod.yml exec db psql -U theogen -d theogen_electoral -c \
    "SELECT id, rut, nombre, ha_votado, token_votacion, familia_id FROM voters WHERE token_votacion = '<TOKEN>';"
  ```
- **Casos habituales:**
  - Si `ha_votado = true`: El token ya fue emitido y confirmado. Se puede consultar el comprobante en la bitácora de auditoría.
  - Si la regla es "Un voto por familia" y `familia_id` coincide con otro miembro de la familia que ya sufragó, la plataforma aplica la restricción familiar por diseño.
