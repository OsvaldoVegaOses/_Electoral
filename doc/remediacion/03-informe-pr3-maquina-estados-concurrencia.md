# Informe de Cierre — PR 3: Máquina de Estados, Congelamiento de Padrón y Voto Familiar Concurrente

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama:** `fix/pr3-state-machine-concurrency`
- **Base:** `fix/pr2-multi-tenant-rbac` (`0b9c334`)
- **Fecha:** 27 de Octubre de 2026
- **Rol:** Ingeniero Principal de Software & Especialista en Seguridad de Sistemas Electorales
- **Estado de la fase:** Completada y Verificada con Pruebas Automatizadas (12/12 tests APROBADOS en PR 3; 35/35 en suite de seguridad; 65/65 en suite total)

---

## 1. Identificación y Descripción de Riesgos Mitigados (P0 / P1)

| ID | Gravedad | Descripción del Riesgo | Impacto Mitigado |
| :--- | :---: | :--- | :--- |
| **RACE-01** | **P0** | **Carrera Concurrente en Voto Familiar.** En la regla "Un voto por familia", diferentes miembros poseen distintos tokens y filas en `voters`. Un `SELECT FOR UPDATE` sobre la fila del votante permitía que dos integrantes emitieran su voto en hilos simultáneos antes del `commit`, duplicando el voto familiar en la urna. | Introducción de la entidad `VotingEntitlement` con clave canónica `unit_key = 'FAM:<ID>'` y restricción única `UniqueConstraint("election_id", "unit_key")`. Todos los miembros contienden sobre el mismo lock y restricción única a nivel de base de datos. |
| **DEADLOCK-01** | **P0** | **Riesgo de Interbloqueo (Deadlock) entre Cierre y Votación.** La concurrencia desordenada entre la transacción de cierre (`POST /elections/{id}/cerrar`) y las transacciones de votación (`POST /voting/submit`) podía trabar la base de datos o generar sufragios extemporáneos. | Jerarquía estricta y consistente de bloqueos: siempre `Election` primero con `with_for_update()`, seguido de `VotingEntitlement`, y finalmente `Voter`. Elimina deadlocks de raíz. |
| **MUT-01** | **P0** | **Alteración Extemporánea del Padrón Electoral.** Se permitía agregar o cargar electores masivamente mientras la elección estaba abierta o cerrada, permitiendo inflar el padrón durante el acto electoral. | Bloqueo absoluto (`409 Conflict`) en `POST /voters`, `POST /voters/upload-excel` y `POST /voters/generate-tokens` si `election.estado != 'Borrador'`. |
| **MUT-02** | **P0** | **Manipulación de Listas y Candidaturas en Curso.** Se permitía agregar o eliminar candidatos con la elección en curso. | Bloqueo absoluto (`409 Conflict`) en `POST /candidates` y `DELETE /candidates/{id}` tras abandonar el estado `Borrador`. |
| **MUT-03** | **P1** | **Alteración de Reglas Estructurales de la Elección.** Se permitía cambiar la regla de votación ("Un voto por persona" a "Un voto por familia") o el colegio vía `PUT /elections/{id}` durante la votación. | Inmutabilidad de campos estructurales (`regla_votacion`, `tipo_votacion`, `school_id`) en elecciones no borradoras (`409 Conflict`), y prohibición de alterar `estado` vía `PUT` general (`400 Bad Request`). |
| **TIME-01** | **P1** | **Vulnerabilidad de Ventana de Votación por Hora del Cliente.** No se validaba la autoridad horaria central en UTC, permitiendo sufragios antes del inicio o después del término programado. | Validación server-side estricta en UTC contra `fecha_inicio` y `fecha_fin` en `/voting/submit`. Rechazo con `409 Conflict` si está fuera de plazo. |
| **STATE-01** | **P1** | **Apertura de Elecciones Inválidas o Vacías.** Se permitía abrir procesos sin electores, sin candidatos o con electores sin `familia_id` en regla familiar. | Validaciones previas obligatorias en `POST /abrir`: padrón no vacío, todos los votantes con `familia_id` si rige regla familiar, al menos una lista regular, coherencia de fechas cronológicas, y sellado con hash SHA-256 (`config_hash`). |
| **STATE-02** | **P1** | **Ausencia de Estado Terminal Definitivo.** No existía una transición formal de archivado que impidiera reaperturas o modificaciones posteriores al escrutinio. | Implementación del estado terminal `Finalizada` (`POST /finalizar`), solo accesible desde `Cerrada`. |

---

## 2. Archivos y Endpoints Modificados

### Backend:
1. `backend/app/models.py`:
   - Incorporación de modelo `VotingEntitlement` (`id`, `election_id`, `unit_key`, `estado`, `fecha_consumo`, `voter_id_consumidor`, `fecha_creacion`) con `UniqueConstraint("election_id", "unit_key")`.
   - Modificación de `Voter`: adición de `rut_normalizado` y `UniqueConstraint("election_id", "rut_normalizado")`.
   - Modificación de `Election`: adición de `config_hash` (SHA-256 de configuración sellada) y relación `entitlements`.
   - Normalización de tipos de fecha a `DateTime(timezone=True)` (`TIMESTAMPTZ` en PostgreSQL) en todos los modelos para garantizar manejo UTC sin desfases de zona horaria local.
2. `backend/app/schemas.py`:
   - Actualización de `ElectionResponse` para exponer `config_hash`.
3. `backend/app/database.py`:
   - Configuración de `connect_args={"options": "-c timezone=utc"}` para conexiones PostgreSQL.
4. `backend/app/routers/voting.py`:
   - Función auxiliar `get_entitlement_key(election, voter)`: calcula clave canónica `FAM:<familia_id>` o `RUT:<rut_normalizado>`.
   - Implementación de orden de locks consistente libre de deadlocks: `Election` (`with_for_update()`) -> `VotingEntitlement` (`with_for_update()`) -> `Voter` (`with_for_update()`).
   - Validación server-side UTC de ventana horaria (`fecha_inicio` y `fecha_fin`).
   - Consumo atómico del derecho electoral en `VotingEntitlement` y marcado del resto de la familia como `Bloqueado`.
   - Protección anti-fuga en `validate_voting_token` con validación de derecho electoral y mensaje genérico de cuota cubierta.
5. `backend/app/routers/elections.py`:
   - Bloqueo de alteración directa de `estado` en `PUT /elections/{id}`.
   - Congelamiento de campos estructurales (`regla_votacion`, `tipo_votacion`, `school_id`) cuando `estado != "Borrador"`.
   - Endpoint `POST /elections/{id}/abrir`: valida padrón no vacío, exigencia de `familia_id` en regla familiar, candidaturas vigentes, orden de fechas, provisionamiento de `VotingEntitlement` y sellado criptográfico `config_hash`.
   - Endpoint `POST /elections/{id}/cerrar`: serializado con `with_for_update()` sobre `Election`.
   - Endpoint `POST /elections/{id}/finalizar`: transición formal a estado terminal `Finalizada`.
   - Endpoint `POST /elections/{id}/comite`: congelado con `409 Conflict` tras apertura.
6. `backend/app/routers/voters.py`:
   - `create_voter`: congelado (`409 Conflict`) si elección no es `Borrador`; almacenamiento obligatorio de `rut_normalizado`.
   - `upload_voters_file`: congelado (`409 Conflict`) si elección no es `Borrador`; inserción de `rut_normalizado`.
   - `generate_all_tokens`: congelado (`409 Conflict`) si elección no es `Borrador`.
7. `backend/app/routers/candidates.py`:
   - `create_candidate`: congelado (`409 Conflict`) si elección no es `Borrador`.
   - `delete_candidate`: congelado (`409 Conflict`) si elección no es `Borrador`.

---

## 3. Matriz de Estados del Proceso Electoral

```
                     ┌───────────┐
                     │           │ (Creación, carga de padrón,
                     │ Borrador  │  inscripción de listas, comités)
                     │           │
                     └─────┬─────┘
                           │ POST /api/elections/{id}/abrir
                           │ (Valida padrón, candidatos, fechas,
                           │  genera config_hash y provisiona entitlements)
                           ▼
                     ┌───────────┐
                     │           │ (Votación activa, padrón y listas congeladas,
                     │  Abierta  │  ventanas horarias UTC vigentes,
                     │           │  escrutinio y actas bloqueados)
                     └─────┬─────┘
                           │ POST /api/elections/{id}/cerrar
                           │ (Bloqueo FOR UPDATE, sella urna digital)
                           ▼
                     ┌───────────┐
                     │           │ (Escrutinio habilitado, generación de acta
                     │  Cerrada  │  definitiva, no admite más votos)
                     │           │
                     └─────┬─────┘
                           │ POST /api/elections/{id}/finalizar
                           │ (Archivo legal definitivo)
                           ▼
                     ┌───────────┐
                     │           │ (Estado terminal inmutable.
                     │ Finalizada│  No admite reaperturas ni votos)
                     │           │
                     └───────────┘
```

---

## 4. Evidencia de Pruebas Automatizadas

Se construyó la suite integral `backend/tests/test_pr3_state_machine_concurrency.py`, ejecutada contra una instancia real de **PostgreSQL 16 en el puerto 5439**:

### A. Pruebas Funcionales de Máquina de Estados y Congelamiento:
1. `test_cannot_open_without_voters`: Rechazo 400 si padrón está vacío. **APROBADO**.
2. `test_cannot_open_family_rule_with_missing_family_id`: Rechazo 400 si electores carecen de `familia_id` bajo regla familiar. **APROBADO**.
3. `test_cannot_open_without_regular_candidates`: Rechazo 400 si no hay candidatos de lista. **APROBADO**.
4. `test_cannot_open_with_incoherent_dates`: Rechazo 400 si `fecha_inicio > fecha_fin`. **APROBADO**.
5. `test_successful_open_provisions_entitlements_and_hash`: Generación de `config_hash` y provisionamiento de `VotingEntitlement`. **APROBADO**.
6. `test_put_election_cannot_change_estado_or_structural_fields`: Rechazo 400 para cambio de estado y 409 para cambio de regla estructural en abierta. **APROBADO**.
7. `test_freezing_candidates_and_padron_when_open`: Rechazo 409 en creación/eliminación de candidatos, electores y comités. **APROBADO**.
8. `test_full_state_lifecycle_to_finalizada`: Ciclo completo `Borrador` -> `Abierta` -> `Cerrada` -> `Finalizada`. **APROBADO**.
9. `test_utc_time_window_restrictions`: Rechazo 409 para votos emitidos antes de inicio o después del cierre UTC. **APROBADO**.

### B. Pruebas de Estrés y Concurrencia sobre PostgreSQL 16 Real:
10. `test_concurrent_votes_same_voter_token_exactly_one_succeeds`:
    - **Condición:** 25 hilos concurrentes simultáneos intentando votar con el **mismo token**.
    - **Resultado:** Exactamente 1 voto aceptado (HTTP 200), 24 votos rechazados (HTTP 409). 1 registro en tabla `Vote`. **APROBADO**.
11. `test_concurrent_votes_same_family_multiple_tokens_exactly_one_succeeds`:
    - **Condición:** 25 hilos concurrentes simultáneos alternando entre dos tokens distintos de la **misma familia** (`FAM-P0-999`).
    - **Resultado:** Exactamente 1 voto familiar aceptado (HTTP 200), 24 votos rechazados (HTTP 409). Entitlement familiar consumido, 1 elector en estado `Votó` y el otro en estado `Bloqueado`. **APROBADO**.
12. `test_concurrent_voting_and_closing_race_no_deadlocks`:
    - **Condición:** 20 hilos concurrentes emitiendo sufragios mientras otro hilo ejecuta simultáneamente el cierre de la elección (`POST /cerrar`).
    - **Resultado:** Cierre exitoso, **0 deadlocks de base de datos** (código 500 no ocurrido), votos aceptados coinciden exactamente con los registros en urna. **APROBADO**.

### Resumen de Ejecución de Suites:
- `test_pr3_state_machine_concurrency.py`: 12/12 tests OK (13.7s).
- Suite integral de remediación (`test_pr1_*.py`, `test_pr2_*.py`, `test_pr3_*.py`): 35/35 tests OK (50.3s).
- Suite de regresión histórica (`verify_all_22_fixes.py`, `verify_security_fixes.py`): 30/30 tests OK.
- **Total verificado:** 65/65 tests APROBADOS.

---

## 5. Riesgos Residuales

1. **Ausencia de Pruebas Criptográficas de Voto Secreto (ZKP / Urna Cifrada):**
   Aunque la integridad transaccional y la unicidad del voto están plenamente resueltas a nivel de base de datos con `VotingEntitlement` y HMAC, el sistema aún asocia en la tabla `Vote` el campo `voter_id` por trazabilidad relacional. Este desacoplamiento definitivo y la garantía de secreto electoral mediante cifrado homomórfico o mezcladores criptográficos es el objeto exclusivo del ADR de Fase D.
2. **Dependencia de Migraciones de Esquema en Caliente:**
   Los nuevos modelos y campos (`VotingEntitlement`, `config_hash`, `rut_normalizado`) requieren la estandarización de migraciones vía Alembic para despliegues desatendidos, lo cual será cubierto en el PR 4.

---

## 6. Próximos Pasos (PR 4)

- Configuración e inicialización de **Alembic** con cadena de migraciones versionadas y reproducibles.
- Auditoría transaccional con patrón Outbox y robustez ante fallas de base de datos.
- Saneamiento y minimización de datos personales (PII) en reportes y exportaciones.
- Robustecimiento del parser de carga masiva de electores (CSV/Excel) con validación estricta y desinfección de fórmulas (protección contra CSV Formula Injection).
- Automatización de integración continua (CI) en GitHub Actions ejecutando pruebas contra PostgreSQL en contenedor.
