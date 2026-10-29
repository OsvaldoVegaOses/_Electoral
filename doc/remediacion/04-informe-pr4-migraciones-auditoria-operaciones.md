# Informe de Cierre — PR 4: Migraciones Alembic, Auditoría Atómica, Sanitización y CI

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama:** `fix/pr4-migrations-audit-operations`
- **Base:** `fix/pr3-state-machine-concurrency` (`670cd82`)
- **Fecha:** 27 de Octubre de 2026
- **Rol:** Ingeniero Principal de Software & Especialista en Seguridad de Sistemas Electorales
- **Estado de la fase:** Implementada — Pendiente de Ejecución de Suite Completa contra PostgreSQL 16

---

## 1. Identificación y Descripción de Riesgos Mitigados (P0 / P1 / P2)

| ID | Gravedad | Descripción del Riesgo | Impacto Mitigado |
| :--- | :---: | :--- | :--- |
| **MIG-01** | **P0** | **Ausencia de Gestión Formal de Esquema de Base de Datos.** El esquema se creaba implícitamente con `Base.metadata.create_all()` en cada arranque, incluso en producción, sin versionamiento, sin trazabilidad de cambios y sin capacidad de reversión controlada. | Integración completa de **Alembic** con migración inicial `a65f5ab1bc4a` que materializa los 9 modelos con índices, restricciones únicas y claves foráneas. Ciclo `upgrade head → downgrade base → upgrade head` verificado sobre PostgreSQL 16 real. DDL automático deshabilitado en producción (`ENVIRONMENT=production`). |
| **MIG-02** | **P1** | **Riesgo de Deriva de Esquema (Schema Drift) entre Entornos.** Sin migraciones formales, los entornos de desarrollo, staging y producción podían divergir silenciosamente. | La migración Alembic es la **fuente única de verdad** del esquema. `env.py` resuelve `DATABASE_URL` desde variable de entorno, garantiza dialecto `psycopg2` y configura `timezone=utc` en conexiones PostgreSQL. |
| **AUDIT-01** | **P1** | **Inconsistencia Transaccional de Auditoría.** El registro de `AuditLog` se ejecutaba con `db.commit()` independiente de la mutación de negocio. Si la operación principal fallaba y se ejecutaba `rollback()`, el registro de auditoría permanecía erróneamente confirmado en la base de datos. | Patrón de auditoría atómica: `log_audit(..., commit=False)` añade la entidad a la sesión activa sin confirmar. El `db.commit()` de la operación de negocio confirma ambos registros (mutación + auditoría) atómicamente, y un `db.rollback()` revierte ambos. Implementado en `create_voter`, `upload_voters_file`, `generate_all_tokens` y `submit_vote`. |
| **PII-01** | **P1** | **Exposición de Datos Personales (PII) en Bitácora de Auditoría.** Los registros de auditoría almacenaban RUT completos de electores en texto claro, accesibles a cualquier operador con permisos de lectura de bitácora. | Función `mask_rut()` que enmascara el cuerpo del RUT preservando los dos primeros dígitos y el verificador (e.g., `16.234.567-2` → `16.***.***-2`). Función `mask_email()` para correos (e.g., `director@colegioa.cl` → `d***r@colegioa.cl`). Ambas aplicadas en registros de auditoría de creación de electores. |
| **INJ-01** | **P0** | **Inyección de Fórmulas CSV/Excel (CSV Formula Injection / DDE).** Los campos alfanuméricos de carga masiva (`nombre`, `curso`, `familia_id`) se almacenaban sin neutralizar. Un archivo Excel o CSV manipulado con payloads como `=cmd|'/C calc'!A0`, `+SUM(A1:A10)`, `@something` o `-100` podía ejecutar comandos del sistema operativo al ser abierto por un operador en Excel/LibreOffice. | Función `sanitize_formula_injection()` que antepone apóstrofe `'` a cualquier valor que inicie con `=`, `+`, `-`, `@`, `\t` o `\r`. Aplicada en carga masiva (`upload_voters_file`) y creación individual (`create_voter`). |
| **UPLOAD-01** | **P1** | **Saturación de Memoria en Carga Masiva de Padrón.** El endpoint `upload-excel` leía el archivo completo en memoria con `await file.read()` sin límite efectivo, permitiendo a un atacante o usuario malintencionado enviar archivos de varios GB y colapsar el servicio. | Lectura en **streaming por chunks de 1 MB** con corte anticipado (`413 Request Entity Too Large`) al superar el límite de 10 MB, sin acumular el contenido completo en RAM antes de validar el tamaño. |
| **UPLOAD-02** | **P1** | **Aceptación de Formato .xls Legado con Superficie de Ataque Amplia.** El formato binario `.xls` (BIFF) posee vectores de ataque conocidos (macros embebidas, explotación de parsers) significativamente mayores que `.xlsx` (ZIP/XML) o `.csv`. | Rechazo explícito con `400 Bad Request` de archivos `.xls`. Solo se aceptan `.xlsx` y `.csv`. |
| **UPLOAD-03** | **P2** | **Pérdida de Ceros a la Izquierda en Columnas Alfanuméricas.** Al leer archivos sin especificar `dtype`, pandas interpretaba columnas como `Familia ID` o `Curso` numéricamente, convirtiendo `007` en `7` y `01A` en un valor corrupto. | Lectura forzada con `dtype=str` tanto en `pd.read_csv()` como en `pd.read_excel()`, preservando intactos los valores alfanuméricos originales. |
| **CI-01** | **P1** | **Ausencia de Pipeline de Integración Continua.** No existía ejecución automática de pruebas ni validación de migraciones en cada push o PR. Las regresiones solo se detectaban manualmente. | Pipeline **GitHub Actions** (`ci.yml`) con dos jobs paralelos: `backend-test` (PostgreSQL 16, Alembic cycle + pytest) y `frontend-build` (Node.js 20, lint + build). Triggers en `push` a ramas `main`, `develop`, `fix/**`, `feat/**` y en `pull_request` a `main`. |
| **DEPLOY-01** | **P1** | **DDL Automático en Producción sin Gobierno.** `Base.metadata.create_all()` se ejecutaba en cada arranque independientemente del entorno, pudiendo generar conflictos con migraciones Alembic o crear tablas sin índices/restricciones esperados. | Condicional en `lifespan()`: DDL automático solo en `development`/`test`; en `production` se emite log informativo y el esquema se gobierna exclusivamente por Alembic. Docker `entrypoint.sh` ejecuta `alembic upgrade head` antes de iniciar Uvicorn. |

---

## 2. Archivos Modificados y Creados

### Backend — Archivos Modificados:
1. `backend/app/auth.py`:
   - Adición de funciones `mask_email(email)` y `sanitize_formula_injection(value)`.
   - Modificación de `log_audit()`: parámetro `commit: bool = True` que permite auditoría atómica dentro de la transacción del llamador cuando `commit=False`.
2. `backend/app/rut_validator.py`:
   - Adición de función `mask_rut(rut)` con enmascaramiento de cuerpo del RUT por asteriscos.
3. `backend/app/routers/voters.py`:
   - `create_voter`: sanitización de fórmulas en `nombre`, `curso` y `familia_id`; auditoría atómica (`commit=False`) con RUT enmascarado en detalle.
   - `upload_voters_file`: lectura en streaming por chunks con corte a 10 MB; rechazo de `.xls`; `dtype=str` en pandas; sanitización de fórmulas en campos alfanuméricos; auditoría atómica.
   - `generate_all_tokens`: auditoría atómica (`commit=False`).
4. `backend/app/routers/voting.py`:
   - `submit_vote`: auditoría atómica (`commit=False`) con `school_id` del proceso electoral.
5. `backend/main.py`:
   - Condicional de entorno para `Base.metadata.create_all()`: deshabilitado en `production`.
6. `backend/requirements.txt`:
   - Adición de dependencia `alembic>=1.13.1`.
7. `backend/Dockerfile`:
   - Inclusión de `chmod +x entrypoint.sh` y cambio de `CMD` a `ENTRYPOINT ["./entrypoint.sh"]`.

### Backend — Archivos Creados:
8. `backend/alembic.ini`:
   - Configuración estándar de Alembic con `script_location`, `prepend_sys_path` y logging.
9. `backend/alembic/env.py`:
   - Función `get_db_url()` con resolución de `DATABASE_URL` desde variable de entorno y corrección automática de dialecto psycopg2.
   - Configuración `connect_args={"options": "-c timezone=utc"}` para PostgreSQL.
   - Soporte para migraciones offline y online con `target_metadata = Base.metadata`.
10. `backend/alembic/versions/a65f5ab1bc4a_initial_schema_pr1_pr3.py`:
    - Migración inicial que materializa las 9 tablas del sistema (`schools`, `users`, `elections`, `voters`, `candidates`, `electoral_committees`, `votes`, `voting_entitlements`, `audit_logs`) con todos los índices, restricciones únicas y claves foráneas definidos en los modelos ORM.
    - Downgrade completo que revierte a esquema vacío en orden de dependencias.
11. `backend/entrypoint.sh`:
    - Script de arranque Docker: ejecuta `alembic upgrade head` antes de iniciar `uvicorn main:app`.

### Infraestructura — Archivos Creados:
12. `.github/workflows/ci.yml`:
    - Job `backend-test`: PostgreSQL 16 como servicio, Python 3.11, instalación de dependencias, ciclo Alembic (`upgrade head → downgrade base → upgrade head`), `pytest tests -v`.
    - Job `frontend-build`: Node.js 20, `npm install`, `npm run lint`, `npm run build`.

### Tests — Archivos Creados:
13. `backend/tests/test_pr4_migrations_audit_operations.py`:
    - Clase `TestPR4PIIAndFormulaSanitization`: tests unitarios de `mask_rut`, `mask_email` y `sanitize_formula_injection`.
    - Clase `TestPR4AtomicAudit`: tests de atomicidad de auditoría con rollback y commit.
    - Clase `TestPR4OperationsAndBulkUpload`: tests de rechazo de `.xls`, corte por streaming a 10 MB (`413`), neutralización de fórmulas en CSV, preservación de ceros a la izquierda y enmascaramiento PII en auditoría.
    - Clase `TestPR4AlembicOnPostgres`: ciclo completo `upgrade → downgrade → upgrade` sobre PostgreSQL 16 real con verificación de tablas e índices.

---

## 3. Diagrama de Flujo de Auditoría Atómica

```
Endpoint (create_voter / upload_voters_file / submit_vote)
  │
  ├─ 1. Ejecutar mutación de negocio (INSERT / UPDATE)
  │     └─ db.add(entity)
  │
  ├─ 2. Registrar auditoría en la misma sesión
  │     └─ log_audit(db, ..., commit=False)
  │           └─ db.add(AuditLog)  ← NO invoca db.commit()
  │
  ├─ 3a. Éxito → db.commit()
  │     └─ AMBOS registros (negocio + auditoría) se confirman atómicamente
  │
  └─ 3b. Error → db.rollback()
        └─ AMBOS registros se revierten: ni la mutación ni la auditoría persisten
```

---

## 4. Cadena de Migraciones Alembic

```
                 ┌──────────────────────────────────┐
                 │     (sin esquema / base vacía)    │
                 └──────────────────┬───────────────┘
                                    │ alembic upgrade head
                                    │
                                    ▼
                 ┌──────────────────────────────────┐
                 │   a65f5ab1bc4a                    │
                 │   "initial_schema_pr1_pr3"        │
                 │                                    │
                 │   9 tablas:                        │
                 │   - schools                        │
                 │   - users (school_id, election_id) │
                 │   - elections (config_hash)         │
                 │   - voters (rut_normalizado)        │
                 │   - candidates                     │
                 │   - electoral_committees            │
                 │   - votes (hash_integridad)         │
                 │   - voting_entitlements (unit_key)   │
                 │   - audit_logs (school_id)           │
                 │                                    │
                 │   Índices: 22                       │
                 │   Restricciones únicas: 4           │
                 │   Claves foráneas: 7                │
                 └──────────────────────────────────┘
                                    │
                                    │ alembic downgrade base
                                    ▼
                 ┌──────────────────────────────────┐
                 │     (esquema vacío / reversión)    │
                 └──────────────────────────────────┘
```

---

## 5. Pipeline de Integración Continua (GitHub Actions)

```
                     ┌──────────────────────┐
                     │  push / pull_request  │
                     │  (main, develop,      │
                     │   fix/**, feat/**)    │
                     └──────────┬───────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
   ┌────────────────────────┐    ┌────────────────────────┐
   │  backend-test           │    │  frontend-build         │
   │  (ubuntu-latest)        │    │  (ubuntu-latest)        │
   │                         │    │                         │
   │  Services:              │    │  Setup: Node.js 20      │
   │  ├─ PostgreSQL 16       │    │                         │
   │  │  (theogen_test)      │    │  Steps:                 │
   │  │                      │    │  ├─ npm install          │
   │  Setup: Python 3.11     │    │  ├─ npm run lint         │
   │                         │    │  └─ npm run build        │
   │  Steps:                 │    │                         │
   │  ├─ pip install         │    └────────────────────────┘
   │  ├─ alembic upgrade     │
   │  ├─ alembic downgrade   │
   │  ├─ alembic upgrade     │
   │  └─ pytest tests -v     │
   │                         │
   │  Env:                   │
   │  ├─ DATABASE_URL        │
   │  ├─ SECRET_KEY          │
   │  └─ VOTE_HMAC_KEY       │
   └────────────────────────┘
```

---

## 6. Evidencia de Pruebas Automatizadas

Se construyó la suite `backend/tests/test_pr4_migrations_audit_operations.py`:

### A. Pruebas de Minimización de Datos (PII) y Sanitización:
1. `test_mask_rut_standard_8_digits`: Enmascaramiento de RUT de 8 dígitos (`16.234.567-2` → `16.***.***-2`). **APROBADO**.
2. `test_mask_rut_7_digits`: Enmascaramiento de RUT de 7 dígitos (`9.876.543-K` → `9.***.***-K`). **APROBADO**.
3. `test_mask_rut_edge_cases`: Casos borde (vacío, `None`, cadena corta → `***`). **APROBADO**.
4. `test_mask_email`: Enmascaramiento de correos (`director@colegioa.cl` → `d***r@colegioa.cl`). **APROBADO**.
5. `test_mask_email_edge_cases`: Casos borde de correo (vacío, `None`, sin `@` → `***`). **APROBADO**.
6. `test_sanitize_formula_injection`: Neutralización de vectores `=`, `+`, `-`, `@`, `\t`, `\r` con apóstrofe. **APROBADO**.
7. `test_sanitize_formula_injection_benign`: Valores benignos pasan sin alteración. **APROBADO**.

### B. Pruebas de Atomicidad Transaccional de Auditoría:
8. `test_atomic_audit_rollback_on_business_failure`: Si `db.rollback()` se ejecuta tras `log_audit(..., commit=False)`, el registro de auditoría **no persiste**. **APROBADO**.
9. `test_atomic_audit_commit_on_business_success`: Si `db.commit()` se ejecuta tras `log_audit(..., commit=False)`, el registro de auditoría **sí persiste** con datos correctos. **APROBADO**.

### C. Pruebas de Operaciones de Carga Masiva y Sanitización End-to-End:
10. `test_upload_rejects_legacy_xls`: Archivo `.xls` rechazado con `400 Bad Request`. **APROBADO**.
11. `test_upload_streaming_rejects_file_exceeding_10mb`: Archivo de 11 MB abortado con `413 Request Entity Too Large` vía streaming. **APROBADO**.
12. `test_upload_csv_sanitizes_formula_injection`: Fórmulas maliciosas en CSV neutralizadas al almacenarse. **APROBADO**.
13. `test_upload_preserves_leading_zeros_dtype_str`: Ceros a la izquierda preservados (`007`, `01A`). **APROBADO**.
14. `test_create_voter_sanitizes_and_masks_pii_in_audit`: Creación individual sanitiza fórmulas y enmascara RUT en auditoría. **APROBADO**.

### D. Pruebas de Migraciones Alembic sobre PostgreSQL 16 Real:
15. `test_alembic_upgrade_downgrade_cycle`: Ciclo completo `upgrade head → downgrade base → upgrade head` sobre PostgreSQL 16 (puerto 5439). Verificación de existencia de las 9+1 tablas e índices críticos. **APROBADO**.

### Resumen de Ejecución de Suites:
- `test_pr4_migrations_audit_operations.py`: **15/15 tests OK**.
- Suite integral de remediación (`test_pr1_*.py`, `test_pr2_*.py`, `test_pr3_*.py`, `test_pr4_*.py`): Pendiente de ejecución consolidada.
- Suite de regresión histórica (`verify_all_22_fixes.py`, `verify_security_fixes.py`): 30/30 tests OK.

---

## 7. Gobierno de Esquema por Entorno

| Entorno | DDL Automático (`create_all`) | Alembic (`upgrade head`) | Seed Demo |
| :--- | :---: | :---: | :---: |
| `development` | **Sí** (arranque FastAPI) | Opcional (manual) | Opt-in (`SEED_DEMO_DATA=true`) |
| `test` | **Sí** (arranque FastAPI) | **Sí** (CI pipeline) | Opt-in (`SEED_DEMO_DATA=true`) |
| `production` | **No** (log informativo) | **Sí** (entrypoint Docker) | **No** (omitido siempre) |

---

## 8. Riesgos Residuales

1. **Persistencia de Sesión JWT en localStorage:**
   Continúa pendiente la migración formal a cookies `HttpOnly; SameSite; Secure` con protección CSRF. El JWT administrativo sigue almacenándose en `localStorage` en el cliente frontend.

2. **Pruebas Criptográficas de Voto Secreto (ZKP / Urna Cifrada):**
   La tabla `Vote` mantiene `voter_id` por trazabilidad relacional. El desacoplamiento criptográfico definitivo es objeto exclusivo del ADR de Fase D (`doc/adr/001-motor-de-votacion.md`).

3. **Cobertura de Tests End-to-End con CI:**
   El pipeline CI ejecuta la suite pytest contra PostgreSQL 16 en contenedor. No incluye aún tests de integración E2E con Playwright/Cypress para el frontend React.

---

## 9. Próximos Pasos (Fase D)

- Redacción y aprobación del **ADR formal** `doc/adr/001-motor-de-votacion.md` para evaluar la integración de Belenios autohospedado vs. diseño de motor propio con pruebas de conocimiento cero (ZKP) y urnas verificables.
- **Prohibición estricta:** No se modificará el núcleo criptográfico ni se declarará la plataforma apta para elecciones vinculantes sin aprobación previa del ADR.
- Migración de sesiones administrativas a cookies `HttpOnly; Secure; SameSite=Strict` con token CSRF sincronizado.
- Evaluación de tests E2E automatizados con Playwright para flujos críticos del frontend.
