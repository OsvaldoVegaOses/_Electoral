# Arquitectura de Bitácora Append-Only y Evidencia Verificable de No Alteración (P15)

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Componente:** Módulo de Auditoría, Integridad y Trazabilidad (`AuditLog`, `backend/app/auth.py`, `backend/app/routers/audit.py`)
- **Fecha:** 27 de Octubre de 2026
- **Rol:** Ingeniero Principal de Software & Especialista en Seguridad de Sistemas Electorales
- **Tarea Sprint 1:** P15 — Bitácora append-only real (no tabla convencional)
- **Estado:** Implementación parcial. La cadena local existe; la serialización PostgreSQL y las pruebas concurrentes deben pasar en CI, y el anclaje externo aún no está acreditado.

---

## 1. Declaración del Problema y Mandato de Seguridad

### 1.1 El problema de la "falsa inmutabilidad"
En las versiones iniciales de la plataforma y en su documentación técnica se catalogaba a la tabla `audit_logs` como *"bitácora legal inmutable"*. Sin embargo, desde una perspectiva estricta de seguridad de la información:

> **Una tabla relacional convencional en PostgreSQL/MySQL NUNCA es inmutable por sí misma.**

Cualquier operador con credenciales administrativas sobre la base de datos (DBA), un atacante que explote una inyección SQL (SQLi), un script de mantenimiento erróneo o un compromiso del motor de persistencia puede ejecutar sentencias como:
```sql
UPDATE audit_logs SET accion = 'Apertura regular' WHERE id = 42;
DELETE FROM audit_logs WHERE accion ILIKE '%falla%';
```
En una tabla estándar, tales operaciones de manipulación no dejan rastro forense dentro de la propia tabla, destruyendo la garantía de no repudio.

### 1.2 La limitación del encadenamiento hash puramente local
El mandato de seguridad del Sprint 1 establece explícitamente:
> *"No llames 'bitácora inmutable' a una tabla convencional. Diseña almacenamiento append-only y evidencia verificable de alteración con anclaje externo/controles independientes si se requiere una garantía fuerte; un encadenamiento hash local sin anclaje no equivale a inmutabilidad."*

Si el sistema solo almacena `hash(prev_hash, datos)` dentro de la misma base de datos, un atacante con acceso `UPDATE` a toda la tabla podría alterar un registro y **recalcular todos los hashes posteriores** hasta la punta de la cadena. Para evitar esto, se requiere un esquema integral de **tres capas independientes de defensa**.

---

## 2. Arquitectura de Defensa en Tres Capas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CAPA 3: ANCLAJE EXTERNO                          │
│   Checkpoints periódicos (POST /api/audit/checkpoint) exportados fuera de   │
│   la base de datos: RFC 3161 TSA, WORM Storage, repositorios independientes │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Garantiza no repudio ante DBA comprometido)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CAPA 2: MOTOR DE BASE DE DATOS                        │
│   Disparador PostgreSQL trg_audit_logs_append_only:                          │
│   - Bloquea UPDATE y DELETE desde los roles de aplicación.                   │
│   - Un DBA privilegiado puede modificar o desactivar el trigger.             │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Enfuerza comportamiento append-only en BD)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CAPA 1: ENCADENAMIENTO CRIPTOGRÁFICO                    │
│   Cadena lineal SHA-256 en aplicación (prev_hash -> record_hash):           │
│   - Detección inmediata de alteración de contenido (record_hash mismatch).  │
│   - Detección inmediata de inserción o borrado de filas (prev_hash break).  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Capa 1: Encadenamiento Criptográfico de Bloques (Hash Chaining)
Cada entrada de auditoría contiene dos campos criptográficos:
- `prev_hash` (`VARCHAR(64)`): El hash del registro inmediatamente precedente. El registro inicial del sistema o génesis utiliza `0000000000000000000000000000000000000000000000000000000000000000` (`GENESIS_HASH`).
- `record_hash` (`VARCHAR(64)`): Digest SHA-256 canónico calculado sobre el contenido del registro y el enlace previo.

### Capa 2: Restricciones a Nivel de Motor de Base de Datos
A través de la migración Alembic `e5f6a7b8c9d0`, se instala en PostgreSQL un disparador procedural (`BEFORE UPDATE OR DELETE`):
- **`UPDATE`**: Prohibido incondicionalmente. Cualquier intento arroja excepción `RAISE EXCEPTION 'Tabla audit_logs es append-only. Operacion % denegada por politica de inmutabilidad.'`.
- **`DELETE`**: Prohibido para los roles normales. Aunque el trigger conserva un mecanismo técnico de mantenimiento, el endpoint de purga está bloqueado con HTTP 409 hasta diseñar retención por épocas y verificar un checkpoint externo. Un DBA privilegiado puede cambiar el trigger; por eso no se declara inmutabilidad.

### Capa 3: Anclaje Externo y Puntos de Verificación (Checkpoints)
La API expone el endpoint `POST /api/audit/checkpoint`. Este endpoint toma el hash del último registro (`head_hash`), el recuento total de eventos y una marca de tiempo en UTC, generando un digest de control (`checkpoint_hash`).
Este hash de control está diseñado para:
1. Publicarse en el acta física de la Comisión Electoral al cerrar los comicios.
2. Enviarse a una Autoridad de Sellado de Tiempo (RFC 3161 TSA).
3. Escribirse en un almacenamiento WORM (Write-Once-Read-Many) en la nube (e.g., AWS S3 Object Lock en modo Compliance).

Solo después de guardar y verificar el artefacto en un custodio independiente se obtiene comparación externa. El endpoint de TheoGen no realiza ese depósito. Su respuesta declara `anchorage_status: PENDIENTE_ANCLAJE_EXTERNO` e `independent_custody_confirmed: false`; no es evidencia de anclaje ni no repudio.

---

## 3. Especificación Técnica de Implementación

### 3.1 Formato Canónico de Hashing
Para evitar discrepancias causadas por serialización de fechas o valores nulos, el digest se calcula de manera estrictamente determinista:

```python
def format_audit_datetime(dt: datetime) -> str:
    """Garantiza representación canónica en UTC: YYYY-MM-DDTHH:MM:SS.ffffffZ"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def compute_audit_hash(prev_hash, fecha, usuario, accion, detalle, school_id) -> str:
    dt_str = format_audit_datetime(fecha)
    u = usuario or ""
    d = detalle or ""
    s = str(school_id) if school_id is not None else ""
    canonical = f"{prev_hash}|{dt_str}|{u}|{accion}|{d}|{s}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

### 3.2 Registro Atómico y Concurrencia
En `log_audit()` ([`backend/app/auth.py`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/backend/app/auth.py)):
1. En PostgreSQL se bloquea la fila singleton `audit_chain_heads` con `SELECT ... FOR UPDATE`, obteniendo un head serializado entre procesos. La fila y el evento se actualizan en la misma transacción.
2. Se genera `record_hash = compute_audit_hash(prev_hash, ...)` y se avanza el head después de insertar el evento.
3. `commit=False` mantiene el evento y el head dentro de la transacción de negocio; `rollback()` descarta ambos.
4. SQLite conserva un camino de desarrollo sin garantías de concurrencia PostgreSQL. La prueba requerida de 100 escritores independientes PostgreSQL 16 solo se considera cumplida cuando CI la ejecuta.

### 3.3 Algoritmo de Verificación de Integridad
Función `verify_audit_log_chain(db)` en [`backend/app/auth.py`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/backend/app/auth.py):
1. Itera por todos los registros ordenados por `id ASC`.
2. Para cada registro $R_i$:
   - Comprueba que el primer `prev_hash` sea `GENESIS_HASH` y que cada registro posterior enlace con el hash anterior. Si no coincide, reporta **eslabón roto** (supresión o inserción no autorizada).
   - Si algún registro legacy no tiene `record_hash`, la verificación falla explícitamente; no se trata como una génesis válida.
   - Recalcula $\text{expected\_hash} = \text{compute\_audit\_hash}(R_i.\text{prev\_hash}, R_i.\text{fecha}, \dots)$. Si difiere de $R_i.\text{record\_hash}$, reporta **contenido alterado** (manipulación de datos).
3. Si todos los eslabones son consistentes, retorna `{"integro": True, "total_revisados": N, ...}`.

La migración S2-D detiene el upgrade si encuentra eventos sin `prev_hash` o `record_hash`: no reescribe historial ni fabrica una génesis retrospectiva. La resolución requiere respaldo, conciliación aprobada y evidencia de que los registros legacy se conservaron. Esta condición puede bloquear el upgrade de una base existente y debe resolverse antes del despliegue.

---

## 4. Endpoints de la API

| Método | Endpoint | Rol Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/audit/logs` | Autenticado (con scoping) | Retorna bitácora con `prev_hash` y `record_hash`. |
| `GET` | `/api/audit/verify-integrity` | `Administrador General` | Ejecuta la verificación criptográfica completa de la cadena. |
| `POST` | `/api/audit/checkpoint` | `Administrador General` | Genera digest SHA-256 para anclaje externo y registra el evento. |
| `POST` | `/api/audit/checkpoint/verify` | `Administrador General` | Verifica un artefacto guardado externamente y el prefijo local correspondiente. |

### Ejemplo de respuesta `/api/audit/verify-integrity`:
```json
{
  "integro": true,
  "total_revisados": 1420,
  "primer_hash": "a1b2c3d4...",
  "ultimo_hash": "f9e8d7c6...",
  "fallo_en_id": null,
  "razon": null,
  "fecha_verificacion": "2026-10-27T19:25:00.000000Z"
}
```

### Forma de respuesta `/api/audit/checkpoint`:
```json
{
  "success": true,
  "timestamp": "2026-10-27T19:25:30.123456Z",
  "total_records": 1420,
  "last_record_id": 1420,
  "head_hash": "f9e8d7c6e5d4c3b2a1...",
  "checkpoint_hash": "3d4f5e6a7b8c9d0e1f2a3b4c5d6e7f8a...",
  "anchorage_status": "PENDIENTE_ANCLAJE_EXTERNO",
  "independent_custody_confirmed": false,
  "instrucciones_anclaje": "Exportar 'checkpoint_hash' a almacenamiento WORM (Write-Once-Read-Many), servidor syslog remoto independiente o Autoridad de Sellado de Tiempo (RFC 3161 TSA) para garantizar no repudio."
}
```

Este objeto ilustra un checkpoint local; no es una constancia de depósito ni una firma externa. El texto y el estado de respuesta deben acompañar siempre cualquier exportación.

---

## 5. Pruebas Automatizadas (Suite P15)

Implementada en [`backend/tests/test_p15_append_only_audit.py`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/backend/tests/test_p15_append_only_audit.py):

| Clase de Test | Caso de Prueba | Resultado |
| :--- | :--- | :---: |
| `TestCryptographicHashChaining` | `test_genesis_record_has_genesis_prev_hash` | **PASSED** |
| `TestCryptographicHashChaining` | `test_subsequent_record_chains_to_previous_hash` | **PASSED** |
| `TestCryptographicHashChaining` | `test_atomic_audit_with_commit_false_chains_correctly` | **PASSED** |
| `TestAuditIntegrityVerification` | `test_verify_returns_integro_true_on_untampered_chain` | **PASSED** |
| `TestAuditIntegrityVerification` | `test_empty_audit_returns_integro_true` | **PASSED** |
| `TestAuditIntegrityVerification` | `test_tamper_detection_modifying_record_action_fails` | **PASSED** |
| `TestAuditIntegrityVerification` | `test_tamper_detection_modifying_record_detail_fails` | **PASSED** |
| `TestAuditIntegrityVerification` | `test_tamper_detection_deleting_record_in_middle_fails` | **PASSED** |
| `TestAuditEndpointsP15` | `test_endpoint_verify_integrity_as_admin` | **PASSED** |
| `TestAuditEndpointsP15` | `test_endpoint_verify_integrity_forbidden_for_non_admin` | **PASSED** |
| `TestAuditEndpointsP15` | `test_endpoint_checkpoint_generates_anchor` | **PASSED** |
| `TestAuditEndpointsP15` | `test_endpoint_checkpoint_forbidden_for_non_admin` | **PASSED** |
| `TestAuditEndpointsP15` | `test_audit_logs_listing_includes_prev_hash_and_record_hash` | **PASSED** |

Las pruebas unitarias locales de cadena y endpoints se han ejecutado. Este resultado no incluye la concurrencia entre procesos en PostgreSQL 16 ni valida custodia externa; la evidencia automatizada de esos gates debe provenir de CI.

---

## 6. Procedimiento Operativo Recomendado para Elecciones

1. **Antes de la Apertura:**
   - La Comisión Electoral solicita al Administrador General ejecutar `GET /api/audit/verify-integrity`.
   - Se ejecuta `POST /api/audit/checkpoint` y se anota el `checkpoint_hash` en el Acta de Instalación de Mesa.
2. **Durante la Votación:**
   - Cada voto, canje de token y evento de administración se encadena en tiempo real de forma transparente.
3. **Al Cierre de la Jornada:**
   - Se ejecuta nuevamente `POST /api/audit/checkpoint`.
   - El `checkpoint_hash` de cierre se imprime en el Acta de Escrutinio y Cierre firmada por los comisionados.
   - La Comisión debe guardar cada artefacto en custodia independiente y registrar el recibo verificable. Hasta entonces, el checkpoint permanece sin anclaje y no permite confrontación externa.

---

## 7. Conclusión

Estado actual:
- Se erradica la denominación engañosa de "tabla inmutable" para la estructura relacional ordinaria.
- Se cuenta con detección criptográfica matemática de manipulación o truncamiento de eventos.
- Hay un mecanismo de serialización PostgreSQL de escritores y un mecanismo de append-only mediante migración; falta la evidencia de ejecución PostgreSQL 16 en CI.
- El endpoint genera y verifica artefactos de checkpoint locales; no existe evidencia de custodio independiente ni anclaje externo confirmado.
- Por tanto, esto no acredita por sí solo no repudio ni habilita GO operacional.
