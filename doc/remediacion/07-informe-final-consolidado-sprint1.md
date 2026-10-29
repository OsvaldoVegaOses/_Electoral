# Informe Final Consolidado de Remediación y Endurecimiento — Sprint 1

- **Proyecto:** TheoGen Electoral
- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama de Entrega:** `fix/pr4-migrations-audit-operations`
- **Commit Base de Diagnóstico:** `0b654e5883145d629f331807693a1db7c9b67134` (27/10/2026)
- **Commit de Cierre del Sprint:** `aa00c5d` (27/10/2026)
- **Rol:** Ingeniero Principal de Software & Especialista en Seguridad de Sistemas Electorales
- **Estado Global:** Sprint 1 **Completado al 100%** (Tareas Críticas P1–P4 e Importantes P5–P15)

---

> [!CAUTION]
> ### DECLARACIÓN IMPERATIVA DE SEGURIDAD Y ALCANCE
> **NO CONFUNDAS CÓDIGO COMPILABLE CON PLATAFORMA ELECTORAL CERTIFICADA.**
> Las remediaciones implementadas en este Sprint 1 endurecen la arquitectura de software, corrigen vulnerabilidades graves (fugas de credenciales, IDOR, inyecciones, manipulación transaccional) y dejan una base operacional reproducible y verificable. Sin embargo, **el sistema actual continúa clasificado como MVP / DEMOSTRACIÓN NO VINCULANTE**.
> Queda **estrictamente prohibido utilizar la plataforma para elecciones oficiales o jurídicamente vinculantes** antes de ejecutar la Prueba de Concepto (Gate G1), resolver los requisitos bloqueantes del **ADR-001** (integración con Belenios 3.3.0 u otro motor auditado) y someter el despliegue final a una auditoría externa independiente.

---

## 1. Resumen Ejecutivo de Vulnerabilidades Remediadas

Durante el Sprint 1 se abordaron y resolvieron **22 vulnerabilidades estructurales** identificadas en el diagnóstico inicial ([`doc/remediacion/00-diagnostico.md`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/remediacion/00-diagnostico.md)), agrupadas en 5 frentes críticos:

1. **Gestión de Credenciales y Sesiones (P0 / P1)**:
   - Se erradicaron los tokens de votación de todas las respuestas de API del padrón, listados de administración y previsualizaciones HTML (`preview_html`).
   - Se suprimió la transmisión de credenciales por parámetros de consulta (`query strings`), trasladando la autenticación de sufragio a cuerpos JSON validados en `POST /api/voting/validate-token` y `POST /api/voting/submit`.
   - Se implementó almacenamiento de credenciales de votación mediante derivación criptográfica **HMAC-SHA256 con sal única (`token_hash`)**, permitiendo la validación y el canje irreversible de la credencial sin persistir el secreto en texto plano en la base de datos (P8).
   - Se eliminaron los tokens JWT de query strings en descargas de actas y PDF, migrando a descarga autenticada por streams Blob.
   - Se migró la persistencia del JWT administrativo desde `localStorage` a **cookies `HttpOnly; Secure; SameSite=Lax`**, complementado con protección **CSRF vía Double Submit Cookie** y un endpoint formal de revocación/cierre de sesión `POST /api/auth/logout` (P2).

2. **Secreto de Resultados y Concurrencia Transaccional (P0)**:
   - Se bloqueó en backend cualquier consulta o filtración de resultados desagregados por candidatura, lista o actas mientras la elección no se encuentre en estado `Cerrada` o `Finalizada`. Durante la votación solo se exponen porcentajes agregados de participación a usuarios autorizados.
   - Se formalizó la **máquina de estados electoral** (`Borrador` → `Abierta` → `Cerrada` → `Finalizada`), congelando de forma atómica e irreversible el padrón de electores, la lista de candidatos, las fechas y las comisiones al momento de la apertura (PR3).
   - Se diseñó el mecanismo de **voto único por familia bajo concurrencia** mediante la tabla `voting_entitlements` con restricción de unicidad `(election_id, unit_key)` y bloqueo pesimista `SELECT ... FOR UPDATE`, eliminando carreras transaccionales de doble voto entre apoderados del mismo hogar.

3. **Aislamiento Organizacional y Control de Acceso (P0 - Anti-IDOR)**:
   - Se implementó segregación server-side estricta basada en membresía institucional (`school_id`) y de proceso (`election_id`), erradicando vulnerabilidades de control de acceso directo a objetos (IDOR).
   - Se formalizó la matriz RBAC de tres niveles: `Administrador General` (atribuciones globales), `Responsable Institucional` (restringido a su colegio) y `Comisión Electoral` (solo lectura de su institución y operación de su elección asignada) (PR2).

4. **Protección de Datos Personales, Sanitización y Bitácora (P1)**:
   - Se neutralizó el riesgo de inyección de fórmulas CSV/Excel (DDE) anteponiendo apóstrofe `'` a campos alfanuméricos (`nombre`, `curso`, `familia_id`).
   - Se implementó lectura de carga masiva en streaming por chunks de 1 MB con corte temprano a 10 MB (`413 Request Entity Too Large`) y rechazo explícito de formatos binarios legados `.xls` (PR4).
   - Se enmascararon el RUT (`16.***.***-2`) y el correo en registros de auditoría y salidas operacionales.
   - Se estableció la **Política de Retención y Eliminación de PII** ([`doc/remediacion/05-politica-retencion-pii.md`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/remediacion/05-politica-retencion-pii.md)) con endpoints de anonimización a 90 días y purga física de auditoría a 365 días (P14).
   - Se diseñó e implementó la **Bitácora Append-Only Criptográfica** ([`doc/remediacion/06-arquitectura-bitacora-append-only.md`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/remediacion/06-arquitectura-bitacora-append-only.md)) con encadenamiento SHA-256 (`prev_hash` y `record_hash`), trigger PostgreSQL bloqueante de `UPDATE`/`DELETE` y endpoints de verificación forense (`/api/audit/verify-integrity`) y anclaje externo (`/api/audit/checkpoint`) (P15).

5. **Infraestructura, Operación y CI (P1 / P2)**:
   - Se reemplazó el rate limiting volátil en memoria por un **Rate Limiter Persistente multi-instancia en Redis** basado en Sliding Window Sorted Sets, con degradación elegante a memoria si Redis no está disponible (P13).
   - Se eliminó el DDL automático en producción (`Base.metadata.create_all()` condicionado a entornos no productivos), gobernando el esquema mediante **Alembic**.
   - Se robustecieron los scripts `backup.sh` y `restore.sh` (variables estrictas `set -u`, modo no interactivo `docker exec -i`, permisos `umask 077` y checksums sha256 relativos) (P11).
   - Se alinearon las directivas Nginx hacia endpoints reales (`/api/voting/submit`, `/api/voting/validate-token`, `/api/auth/login`) (P10).
   - Se implementó pipeline de Integración Continua en GitHub Actions (`ci.yml`) con escaneo automático de vulnerabilidades (`pip-audit`) y secretos (`gitleaks`) (P5).
   - Se fijaron todas las dependencias con versiones exactas (`==`) en `requirements.txt` (P12).
   - Se implementó healthcheck activo con verificación real de conectividad a la base de datos (`SELECT 1`) (P7).

---

## 2. Listado Cronológico de Commits y Entregables

| Commit | Mensaje / Entregable | Fase / Tarea |
| :---: | :--- | :---: |
| `0b654e5` | Initial commit - TheoGen Electoral MVP base | Línea base |
| `ddf489d` | `doc/remediacion/00-diagnostico.md`: Informe inicial de auditoría | Diagnóstico |
| `9fe2a9d` | `test_pr1_security_containment.py`: Suite de contención de seguridad | PR 1 (Tests) |
| `52a3389` | Contención de tokens en URL, query strings, escrutinio en vivo y rate limit | PR 1 (Backend) |
| `bdc0b74` | Frontend: consumo seguro de API de votación, descarga Blob de actas | PR 1 (Frontend) |
| `637a8a5` | `doc/remediacion/01-informe-pr1-contencion.md`: Cierre formal de PR 1 | PR 1 (Docs) |
| `0b9c334` | Aislamiento organizacional multi-tenant, matriz RBAC y server-side anti-IDOR | PR 2 |
| `670cd82` | Máquina de estados formal, padrón congelado y voto familiar transaccional concurrente | PR 3 |
| `9c2ddb6` | Migraciones Alembic, auditoría atómica, sanitización CSV y CI GitHub Actions | PR 4 |
| `d4ec3ab` | Mejoras operacionales: README (P3), escaneo CI (P5), CORS (P6), healthcheck (P7), requirements (P12) | P3, P5–P7, P12 |
| `6bbf02c` | JWT a cookies HttpOnly, protección CSRF Double Submit y logout seguro | P2 |
| `c2ed499` | Hasheo HMAC-SHA256 de tokens (P8), tests E2E Playwright (P9), validación Docker/Nginx (P10) | P8, P9, P10 |
| `eac151c` | Verificación y endurecimiento estricto de scripts `backup.sh` y `restore.sh` | P11 |
| `66d6de6` | Rate limiting persistente distribuido con Redis (Sliding Window Sorted Sets) | P13 |
| `cf9657a` | Política de retención de PII, migración y endpoints de anonimización y purga | P14 |
| `c89f3d3` | Bitácora append-only criptográfica (SHA-256), trigger PostgreSQL y anclaje/checkpoints | P15 |
| `aa00c5d` | Formalización de ADR-001 de selección de motor (Belenios 3.3.0 condicional vs motor propio) | P1 |

---

## 3. Matriz de Trazabilidad: Hallazgo → Severidad → Corrección → Prueba → Resultado

| ID Hallazgo | Sev. | Vulnerabilidad / Defecto | Corrección Implementada | Prueba de Verificación | Resultado |
| :--- | :---: | :--- | :--- | :--- | :---: |
| **SEC-01** | **P0** | Tokens de votación en query strings de URLs | Migración a body JSON en endpoints de votación | `test_pr1_security_containment.py` | **PASSED** |
| **SEC-02** | **P0** | Escrutinio en vivo expuesto antes del cierre | Bloqueo server-side de resultados hasta estado Cerrada | `test_pr1_security_containment.py` | **PASSED** |
| **SEC-03** | **P0** | JWT en query strings para descarga de actas | Descarga vía cabecera `Authorization` en streams Blob | Inspección de API y llamadas HTTP | **PASSED** |
| **SEC-04** | **P0** | Tokens en texto plano en respuestas de padrón | Eliminación de `token_votacion` de schemas de lectura | `test_pr1_security_containment.py` | **PASSED** |
| **RBAC-01** | **P0** | Ausencia de roles granulares en backend | Matriz RBAC tripartita (`Superadmin`, `Responsable`, `Comisión`) | `test_pr2_rbac_multitenancy.py` | **PASSED** |
| **IDOR-01** | **P0** | Fuga de colegios entre instituciones (IDOR) | Scoping forzado por `user.school_id` del lado servidor | `test_pr2_rbac_multitenancy.py` | **PASSED** |
| **IDOR-02** | **P0** | Modificación de elecciones ajenas | Validación cruzada de pertenencia de colegio y proceso | `test_pr2_rbac_multitenancy.py` | **PASSED** |
| **STATE-01** | **P0** | Modificación de padrón tras apertura de mesa | Máquina de estados con congelamiento estricto | `test_pr3_state_machine_concurrency.py` | **PASSED** |
| **STATE-02** | **P0** | Transición arbitraria de estados por PUT | Endpoint dedicados (`/abrir`, `/cerrar`, `/finalizar`) | `test_pr3_state_machine_concurrency.py` | **PASSED** |
| **RACE-01** | **P0** | Doble voto familiar en concurrencia | `voting_entitlements` con `SELECT ... FOR UPDATE` | `test_pr3_state_machine_concurrency.py` | **PASSED** |
| **MIG-01** | **P0** | DDL automático desgobernado en arranque | Deshabilitación de `create_all` en prod; control Alembic | `TestPR4AlembicOnPostgres` | **PASSED** |
| **INJ-01** | **P0** | Inyección de fórmulas CSV/Excel (DDE) | Prefijo `'` forzado a caracteres `=`, `+`, `-`, `@`, `\t` | `test_pr4_migrations_audit_operations.py` | **PASSED** |
| **P2-AUTH** | **P1** | JWT vulnerable en `localStorage` | Migración a cookies `HttpOnly; Secure` + CSRF Double Submit | `test_p2_httponly_cookies_csrf.py` | **PASSED** |
| **P8-HASH** | **P1** | Tokens de sufragio en texto plano en BD | Hasheo HMAC-SHA256 (`token_hash`) y consumo irreversible | `test_p8_token_hashing.py` | **PASSED** |
| **P13-RATE** | **P1** | Rate limit en memoria vulnerable a multi-instancia | Backend Redis Sliding Window con fallback memoria | `test_p13_rate_limiting_redis.py` | **PASSED** |
| **P14-PII** | **P1** | Retención indefinida de datos personales | Política formal, anonimización padrón y purga audit | `test_p14_pii_retention.py` | **PASSED** |
| **P15-LOGS** | **P1** | Bitácora mutable sujeta a manipulación DBA | Hash Chaining SHA-256, trigger PG y anclaje/checkpoints | `test_p15_append_only_audit.py` | **PASSED** |
| **UPLOAD-01** | **P1** | Denegación de servicio por archivos gigantes | Streaming chunks 1 MB con corte a 10 MB (`413`) | `test_pr4_migrations_audit_operations.py` | **PASSED** |
| **UPLOAD-02** | **P1** | Formato binario `.xls` inseguro | Rechazo estricto de `.xls` (solo `.xlsx` y `.csv`) | `test_pr4_migrations_audit_operations.py` | **PASSED** |
| **UPLOAD-03** | **P2** | Pérdida de ceros en columnas alfanuméricas | Lectura forzada `dtype=str` en pandas | `test_pr4_migrations_audit_operations.py` | **PASSED** |
| **OPS-01** | **P2** | Falta de healthcheck activo a base de datos | Endpoint `/api/health` con consulta activa `SELECT 1` | `test_pr4_migrations_audit_operations.py` | **PASSED** |
| **OPS-02** | **P2** | CORS no configurable en producción | Variable `BACKEND_CORS_ORIGINS` con parseo seguro | `test_pr4_migrations_audit_operations.py` | **PASSED** |

---

## 4. Cadena de Migraciones Alembic

El esquema de base de datos evolucionó a través de **4 migraciones controladas, reproducibles y reversibles**:

```
[Base Vacía]
     │
     ▼ (alembic upgrade a65f5ab1bc4a)
┌────────────────────────────────────────────────────────┐
│ a65f5ab1bc4a: initial_schema_pr1_pr3                   │
│ Materializa las 9 tablas base:                         │
│ schools, users, elections, voters, candidates,         │
│ electoral_committees, votes, voting_entitlements,      │
│ audit_logs. 22 índices, 4 restricciones de unicidad.   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (alembic upgrade c78d9e0f1a2b)
┌────────────────────────────────────────────────────────┐
│ c78d9e0f1a2b: add_token_hash_to_voters (P8)           │
│ Agrega columna token_hash (String 64) e índice único.  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (alembic upgrade d4e5f6a7b8c9)
┌────────────────────────────────────────────────────────┐
│ d4e5f6a7b8c9: add_pii_eliminado_en (P14)               │
│ Agrega columna pii_eliminado_en en voters y comisiones.│
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼ (alembic upgrade e5f6a7b8c9d0)
┌────────────────────────────────────────────────────────┐
│ e5f6a7b8c9d0: add_audit_log_hash_chain (P15)           │
│ Agrega prev_hash, record_hash y disparador PostgreSQL  │
│ trg_audit_logs_append_only que prohíbe UPDATE/DELETE.  │
└────────────────────────────────────────────────────────┘
```
Todas las migraciones cuentan con su método `downgrade()` correspondiente, asegurando rollback seguro en caso de contingencia.

---

## 5. Riesgos Críticos que Aún Bloquean el Paso a Producción

Aunque el backend y frontend han alcanzado un estándar de ingeniería robusto y seguro a nivel operacional, existen **cinco riesgos estructurales insalvables** que impiden autorizar elecciones vinculantes:

1. **Acoplamiento Directo en el Modelo `Vote` (Secreto del Voto Comprometido)**:
   - La tabla `votes` almacena en la misma fila `voter_id` y `candidate_id`. Un administrador del servidor puede correlacionar directamente la identidad del elector con su voto. Eliminar la columna `voter_id` sin un protocolo criptográfico no resuelve el problema, ya que la correlación persiste por marcas de tiempo en `fecha_voto`, registros de red y orden de inserción.
2. **Correlación por Tamaño de Muestra (Urnas Pequeñas)**:
   - En votaciones de cursos pequeños (e.g. 20–30 electores), la publicación de resultados desagregados o patrones de concurrencia permite inferir opciones de sufragio por descarte contextual.
3. **Ausencia de Verificabilidad Criptográfica de Extremo a Extremo (E2E-V)**:
   - El sistema actual no genera pruebas de conocimiento cero (ZKP) ni boletas cifradas homomórficamente en el navegador del votante. La confianza recae íntegramente en la honestidad del servidor de TheoGen.
4. **Incertidumbre Estatutaria y Normativa Chilena**:
   - Cada Centro de Padres u organización tiene una personalidad jurídica distinta (Ley 19.418, D.S. 565/1990 o de hecho). Muchos estatutos exigen asamblea presencial o boleta en papel; utilizar votación electrónica remota sin reforma estatutaria previa expone la elección a impugnación ante el Tribunal Electoral Regional (TER).
5. **Entrada en Vigor de la Ley 21.719 (Protección de Datos Personales)**:
   - Con vigencia obligatoria desde el **01/12/2026**, la gestión de padrones escolares exigirá evaluaciones de impacto (DPIA), designación de encargado de datos y estrictas cláusulas de responsabilidad que deben formalizarse antes de operar comercialmente.

---

## 6. Evidencia de Pruebas y Demo Operativa

Durante el Sprint 1 se ejecutaron y validaron las siguientes suites de pruebas:

- **E2E Playwright** ([`backend/tests/e2e/test_voting_e2e.py`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/backend/tests/e2e/test_voting_e2e.py)):
  Flujos automatizados de navegación real en Chromium: autenticación de votante con credencial válida, sufragio en urna, verificación de comprobante, rechazo de credenciales agotadas y bloqueo de sufragios en elecciones cerradas (**PASSED**).
- **Pruebas de Regresión y Seguridad Backend**:
  - `test_pr1_security_containment.py`: 8/8 pruebas aprobadas (**PASSED**).
  - `test_pr2_rbac_multitenancy.py`: 13/13 pruebas aprobadas (**PASSED**).
  - `test_pr3_state_machine_concurrency.py`: 15/15 pruebas aprobadas (**PASSED**).
  - `test_p2_httponly_cookies_csrf.py`: Aprobado (**PASSED**).
  - `test_p8_token_hashing.py`: Aprobado (**PASSED**).
  - `test_p10_docker_and_nginx_validation.py`: Aprobado (**PASSED**).
  - `test_p13_rate_limiting_redis.py`: 13/13 pruebas aprobadas (**PASSED**).
  - `test_p14_pii_retention.py`: 12/12 pruebas aprobadas (**PASSED**).
  - `test_p15_append_only_audit.py`: 13/13 pruebas aprobadas (**PASSED**).
- **Herramientas de Infraestructura**:
  - `docker compose config`: Sintaxis y variables validadas sin errores.
  - `nginx -t`: Sintaxis y directivas de mitigación validadas.
  - `backup.sh` / `restore.sh`: Validación de dry run con `set -u` y verificación SHA-256 completada.

---

## 7. Recomendaciones Priorizadas para la Siguiente Fase

### Prioridad Alta (Inmediata - Técnica):
1. **Ejecutar Gate G1 del ADR-001**: Montar un entorno de prueba de concepto aislado con **Belenios 3.3.0 autohospedado**, evaluando su API documentada (`/api/`) para verificar si admite el flujo de credenciales y la política de revoto requerida por TheoGen.
2. **Preservar TheoGen como Capa de Gobierno**: Mantener el backend actual de TheoGen para la administración de instituciones, convocatorias, padrón escolar con RUT y generación de actas legales.

### Prioridad Media (Organizacional y Legal):
3. **Revisión Estatutaria por Colegio**: Exigir a cada institución educativa certificar si sus estatutos admiten votación electrónica remota y si su regla es "un voto por apoderado" o "un voto por familia".
4. **Segregación de Roles Electorales**: Formalizar la designación de autoridades independientes: un *Credential Operator* externo para la custodia de semillas de sufragio y al menos tres *Trustees* independientes (e.g. 2 de 3) para el descifrado umbral.

### Prioridad Baja (Mantenimiento Continuo):
5. **Auditoría Externa de Código**: Someter la integración final a un pentest y revisión de código por un tercero acreditado antes de remover la etiqueta de "Demostración no vinculante".

---

## 8. Lista Corta de Decisiones Requeridas por el Dueño del Proyecto

Para definir el rumbo posterior a este Sprint 1, el responsable y dueño del proyecto debe pronunciarse explícitamente sobre **5 decisiones estratégicas**:

1. **Aprobación de la Prueba de Concepto (Gate G1 de ADR-001)**:
   - *Decisión:* ¿Se aprueba formalmente destinar recursos para desplegar una instancia de laboratorio de **Belenios 3.3.0** y medir experimentalmente su integración con TheoGen Electoral?
2. **Definición de la Política de Revoto**:
   - *Decisión:* ¿Se adoptará estatutariamente la política **R1 (el votante puede corregir su voto hasta el cierre; cuenta el último emitido)** o se exige **R2 (primer voto irrevocable)**? *(Nota: Belenios implementa R1 de forma nativa; exigir R2 podría obligar a descartar Belenios)*.
3. **Modelo Jurídico de Representación Familiar**:
   - *Decisión:* En elecciones de Centros de Padres con regla familiar, ¿se establecerá el requisito de que la familia acredite a **un único apoderado titular** antes del congelamiento del padrón para recibir la credencial de votación?
4. **Estructura de Custodia de Autoridades (Trustees)**:
   - *Decisión:* ¿Quiénes asumirán la custodia de las partes de la clave de descifrado en los colegios (e.g., Director, Presidente TRICEL, Representante de Apoderados)?
5. **Presupuesto y Cronograma de Auditoría Externa**:
   - *Decisión:* ¿Se cuenta con el presupuesto para encargar una auditoría externa independiente previa al primer comicio vinculante (Gate G4)?

---

## 9. Conclusión del Sprint 1

El Sprint 1 ha cerrado satisfactoriamente todas las brechas operacionales, de control de acceso, de concurrencia y de trazabilidad forense identificadas en el sistema. 

El repositorio queda en un estado limpio, ordenado, automatizado con CI y con su hoja de ruta criptográfica formalmente establecida en el [ADR-001](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/adr/001-motor-de-votacion.md).
