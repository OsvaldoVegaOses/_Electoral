# Política de Retención y Eliminación de Datos Personales (PII)
## TheoGen Electoral — Documento Interno de Privacidad

**Versión:** 1.0  
**Fecha:** 2026-10-27  
**Estado:** Vigente  
**Alcance:** Todas las instalaciones del sistema TheoGen Electoral  
**Autor:** Equipo de Desarrollo TheoGen  

---

## 1. Propósito

Este documento define qué datos personales (PII — *Personally Identifiable Information*) almacena TheoGen Electoral, cuánto tiempo los retiene, cómo se eliminan o anonimizan, y quién es responsable de ejecutar cada acción.

> **Aviso legal:** TheoGen Electoral es un sistema de votación para organizaciones educativas, centros de padres y organizaciones comunitarias. **No está certificado como plataforma electoral oficial.** El tratamiento de datos personales debe ajustarse a la Ley N° 19.628 sobre Protección de la Vida Privada (Chile) y sus modificaciones.

---

## 2. Inventario de Datos Personales

### 2.1 Tabla `voters` — Padrón Electoral

| Campo | Categoría PII | Sensibilidad | Propósito |
|---|---|---|---|
| `rut` | Identificador nacional | 🔴 Alta | Identificación del elector |
| `rut_normalizado` | Identificador nacional | 🔴 Alta | Unicidad y búsqueda |
| `nombre` | Datos personales | 🟡 Media | Identificación |
| `correo` | Datos de contacto | 🟡 Media | Comunicación (opcional) |
| `familia_id` | Agrupación familiar | 🟡 Media | Regla de sufragio familiar |
| `token_votacion` | Credencial de acceso | 🔴 Alta | Autenticación (NULL tras votar) |
| `token_hash` | Hash de credencial | 🟠 Media-Alta | Verificación segura (NULL tras votar) |
| `estado` | Estado de participación | 🟢 Baja | Control de proceso |
| `fecha_voto` | Metadato temporal | 🟢 Baja | Trazabilidad del proceso |

### 2.2 Tabla `users` — Administradores del Sistema

| Campo | Categoría PII | Sensibilidad | Propósito |
|---|---|---|---|
| `nombre` | Datos personales | 🟡 Media | Identificación del operador |
| `email` | Datos de contacto | 🟡 Media | Autenticación y comunicación |
| `password_hash` | Credencial derivada | 🔴 Alta | Autenticación (bcrypt) |

### 2.3 Tabla `electoral_committees` — Miembros de Comisiones

| Campo | Categoría PII | Sensibilidad | Propósito |
|---|---|---|---|
| `nombre` | Datos personales | 🟡 Media | Identificación del comisionado |
| `rut` | Identificador nacional | 🔴 Alta | Identificación |
| `correo` | Datos de contacto | 🟡 Media | Comunicación (opcional) |

### 2.4 Tabla `audit_logs` — Bitácora de Auditoría

| Campo | Categoría PII | Sensibilidad | Propósito |
|---|---|---|---|
| `usuario` | Email enmascarado | 🟡 Media | Trazabilidad de acciones |
| `detalle` | Texto libre | 🟡 Variable | Descripción de la acción |

> ⚠️ El campo `audit_logs.usuario` almacena emails enmascarados (ej. `d***r@colegio.cl`) — NO el email completo — gracias a la función `mask_email()` implementada en `app/auth.py`.

### 2.5 Tabla `schools` — Instituciones

| Campo | Categoría PII | Sensibilidad | Propósito |
|---|---|---|---|
| `correo_contacto` | Datos de contacto institucional | 🟢 Baja | Información de contacto |
| `telefono` | Datos de contacto institucional | 🟢 Baja | Información de contacto |

---

## 3. Períodos de Retención

| Entidad | Período de retención | Justificación | Acción al vencimiento |
|---|---|---|---|
| **Padrón electoral** (`voters`) | 90 días tras finalizar la elección | Recurso de impugnación/revisión | Anonimización de RUT, nombre y correo |
| **Credenciales** (`token_votacion`, `token_hash`) | Eliminadas al votar (inmediato) | No se requieren tras el canje | `NULL` en ambos campos al emitir voto (ya implementado en P8) |
| **Miembros de comisión** (`electoral_committees`) | 90 días tras finalizar la elección | Mismo período de recurso | Anonimización de RUT, nombre y correo |
| **Usuarios administradores** (`users`) | Indefinido mientras la cuenta esté activa | Necesidad operativa | Eliminación manual por superadmin |
| **Bitácora de auditoría** (`audit_logs`) | 365 días | Cumplimiento y trazabilidad | Eliminación de registros antiguos |
| **Logs de aplicación** (archivos) | 90 días | Seguridad operacional | Rotación automática (logrotate) |

> **Nota:** Los períodos aquí definidos son valores por defecto razonables para el contexto chileno. La organización responsable de la instalación puede ajustarlos en el archivo `.env` mediante las variables `PII_VOTER_RETENTION_DAYS`, `PII_AUDIT_RETENTION_DAYS`.

---

## 4. Mecanismo de Anonimización

TheoGen implementa **anonimización en lugar de eliminación** para las tablas `voters` y `electoral_committees` una vez vencido el período de retención. Esto se hace por dos razones:

1. Preservar la integridad referencial de la tabla `votes` (que usa `voter_id` como referencia)
2. Mantener estadísticas de participación sin datos identificables

### 4.1 Proceso de Anonimización de Electores

Al ejecutar la anonimización de un registro `voters`:

```
rut              → "[ANONIMIZADO]"
rut_normalizado  → "[ANONIMIZADO]"
nombre           → "[Elector Anonimizado]"
correo           → NULL
familia_id       → NULL (si no afecta estadísticas de voto familiar)
token_votacion   → NULL (ya debería ser NULL tras votar)
token_hash       → NULL (ya debería ser NULL tras votar)
```

El campo `pii_eliminado_en` (timestamp) se establece para indicar que el registro fue procesado y evitar doble procesamiento.

### 4.2 Proceso de Anonimización de Comisiones

```
nombre   → "[Comisionado Anonimizado]"
rut      → "[ANONIMIZADO]"
correo   → NULL
```

### 4.3 Proceso de Eliminación de Auditoría Antigua

Los registros de `audit_logs` con más de `PII_AUDIT_RETENTION_DAYS` días se **eliminan físicamente** (no hay referencia de integridad que preservar).

---

## 5. Procedimiento Operativo

### 5.1 Ejecución Manual (recomendada)

```bash
# Verificar qué elecciones son candidatas a anonimización
curl -H "Authorization: Bearer <JWT_ADMIN>" \
  https://tu-dominio.com/api/admin/pii/elections-ready-for-anonymization

# Ejecutar anonimización para una elección específica
curl -X POST -H "Authorization: Bearer <JWT_ADMIN>" \
  https://tu-dominio.com/api/admin/pii/anonymize-election/{election_id}

# Ejecutar limpieza de logs de auditoría antiguos
curl -X POST -H "Authorization: Bearer <JWT_ADMIN>" \
  https://tu-dominio.com/api/admin/pii/purge-audit-logs
```

### 5.2 Automatización (crontab recomendado)

```bash
# Ejecutar limpieza de PII diariamente a las 02:00 AM
0 2 * * * /usr/local/bin/theogen-pii-cleanup.sh
```

### 5.3 Script de Limpieza (`theogen-pii-cleanup.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
# Requiere: ADMIN_JWT configurado como secreto del sistema
API_BASE="${API_BASE:-https://localhost:8000}"
curl -sf -X POST "${API_BASE}/api/admin/pii/purge-audit-logs" \
  -H "Authorization: Bearer ${ADMIN_JWT}" | jq .
```

---

## 6. Variables de Configuración

Agregar al archivo `.env` para personalizar períodos:

```ini
# Días tras Finalización de elección antes de anonimizar padrón y comisiones
PII_VOTER_RETENTION_DAYS=90

# Días de retención de registros de auditoría
PII_AUDIT_RETENTION_DAYS=365
```

---

## 7. Datos que NO se eliminan / justificación

| Dato | Razón de retención permanente |
|---|---|
| `votes.candidate_id` + `votes.election_id` | Resultado electoral; no contiene PII directa tras anonimizar `voters` |
| `votes.hash_integridad` | Prueba criptográfica de integridad del acta |
| `elections.*` | Registro histórico del proceso electoral (sin PII) |
| `voting_entitlements.unit_key` | `"FAM:X"` o `"RUT:XX"` sin nombre/correo; conservar para integridad estadística |

> ⚠️ `voting_entitlements.unit_key` puede contener el RUT normalizado en formato `"RUT:XXXXXXXX-X"`. Tras la anonimización del padrón, este campo queda como un identificador técnico sin correlación visible con el nombre o correo del elector.

---

## 8. Registro de Ejecuciones

Cada ejecución de anonimización o purga debe quedar registrada en la bitácora de auditoría (`audit_logs`) con la acción `"PII: Anonimización de padrón"` o `"PII: Purga de auditoría"`, el número de registros afectados, y el usuario administrador que la solicitó.

---

## 9. Riesgos Residuales Conocidos

| Riesgo | Nivel | Mitigación |
|---|---|---|
| Correlación `voter_id` ↔ `candidate_id` en tabla `votes` | 🔴 Alto | Bloqueado por ADR de motor criptográfico (pendiente P1) |
| `voting_entitlements.unit_key` contiene RUT normalizado | 🟡 Medio | Valor técnico sin nombre; riesgo bajo post-anonimización |
| Backups anteriores a la anonimización contienen PII | 🟡 Medio | Política de retención de backups: eliminar backups > 90 días (ver `backup.sh`) |
| Logs de aplicación en disco con PII en trazas de error | 🟠 Medio-Alto | Revisar nivel de logging; nunca loguear RUT/nombre en nivel DEBUG en producción |

---

*Documento generado automáticamente como parte del sprint de hardening. Revisar anualmente o ante cambios normativos.*
