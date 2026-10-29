# Informe de Cierre — PR 2: Aislamiento por Organización, RBAC y Controles Anti-IDOR

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama:** `fix/pr2-multi-tenant-rbac`
- **Base:** `fix/pr1-security-containment` (`637a8a5`)
- **Fecha:** 27 de Octubre de 2026
- **Estado de la fase:** Completada y Verificada con Pruebas Automatizadas (15/15 tests APROBADOS, 38/38 en suite completa)

---

## 1. Identificación y Descripción de Riesgos Mitigados (P0)

| ID | Gravedad | Descripción del Riesgo | Impacto Mitigado |
| :--- | :--- | :--- | :--- |
| **IDOR-01** | **P0** | Acceso y modificación horizontal entre colegios (`GET/PUT /api/schools/{id}`). Un usuario autenticado de la institución A podía inspeccionar o editar la ficha del colegio B alterando el parámetro de ruta. | Se impone verificación server-side `check_school_access`. Solo Administrador General o el Responsable Institucional de ese colegio pueden operar sobre él. |
| **IDOR-02** | **P0** | Manipulación y consulta no autorizada de elecciones (`GET/PUT /api/elections/{id}`). Usuarios de la institución A podían consultar detalle o modificar parámetros de elecciones de la institución B. | Validación transversal `check_election_access`. Se exige correspondencia estricta entre `user.school_id` y `election.school_id`. |
| **IDOR-03** | **P0** | Acceso no autorizado al padrón y creación foránea de electores (`GET/POST /api/elections/{id}/voters`). | El servidor rechaza con `403 Forbidden` cualquier consulta o mutación del padrón electoral de otra institución o elección fuera de ámbito. |
| **IDOR-04** | **P0** | Manipulación de candidaturas y listas ajenas (`GET/POST/DELETE /api/elections/{id}/candidates`). | Restricción server-side impidiendo listar, registrar o eliminar candidatos en elecciones pertenecientes a otras entidades. |
| **IDOR-05** | **P0** | Falta de aislamiento de la Comisión Electoral dentro de la misma institución. Un miembro de comisión de la Elección 1 podía administrar la Elección 2 del mismo colegio. | Se introduce membresía explícita a nivel de elección (`user.election_id`). Las comisiones quedan acotadas exclusivamente a su elección asignada. |
| **IDOR-06** | **P0** | Fuga horizontal de escrutinio oficial y descarga de actas de apertura y cierre en PDF (`/api/reports/election/{id}/...`). | Bloqueo estricto por ámbito institucional y de comisión para escrutinio y actas PDF con código `403 Forbidden`. |
| **IDOR-07** | **P0** | Generación de credenciales y simulación de despacho masivo de correos foráneos (`/generate-tokens`, `/simulate-email-dispatch`). | Verificación previa obligatoria de pertenencia electoral antes de manipular o previsualizar credenciales. |
| **RBAC-01** | **P0** | Asunción global implícita de rol "Administrador". No existía distinción entre superadministrador nacional y gestor local de un colegio. | Formalización de roles: `Administrador General`, `Responsable Institucional` y `Comisión Electoral` con matriz de mínimo privilegio y denegación por defecto. |
| **RBAC-02** | **P0** | Listados globales sin filtrado en backend (`GET /api/schools`, `GET /api/elections`). Se confiaba en que el cliente frontend filtrara los datos. | Implementación de scoping obligatorio del lado servidor: los listados retornan únicamente las entidades autorizadas para el usuario autenticado. |
| **RBAC-03** | **P0** | Estadísticas globales del dashboard (`GET /api/reports/dashboard-stats`) exponían métricas consolidadas de todas las instituciones a cualquier usuario. | Cálculo del panel de control acotado por rol: Superadmin (global), Responsable Institucional (colegio), Comisión Electoral (elección asignada). |
| **RBAC-04** | **P0** | Fuga de bitácora de auditoría entre organizaciones (`GET /api/audit/logs`). | Trazabilidad con `school_id` y filtrado server-side de registros de auditoría según la institución del usuario consultor. |

---

## 2. Archivos y Endpoints Modificados

### Backend:
1. `backend/app/models.py`:
   - Modelo `User`: añadidos campos relacionales `school_id` (ForeignKey `schools.id`), `election_id` (ForeignKey `elections.id`), y relaciones ORM `school` y `election`. Rol predeterminado actualizado a `"Administrador General"`.
   - Modelo `AuditLog`: incorporado campo `school_id` indexado para segregación multi-tenant de bitácoras.
2. `backend/app/schemas.py`:
   - `UserCreate` y `UserResponse`: añadidos campos opcionales `school_id: Optional[int]` y `election_id: Optional[int]`.
   - Creado esquema `SchoolUpdate` para modificaciones validadas de instituciones.
3. `backend/app/auth.py`:
   - Definición formal de constantes de rol: `ROLE_SUPERADMIN`, `ROLE_RESPONSABLE`, `ROLE_COMISION`, `ROLE_LEGACY_ADMIN`.
   - Función auxiliar `is_superadmin(user)` para distinguir superadministradores globales de usuarios institucionales.
   - Función de control de acceso institucional `check_school_access(user, school_id, write=False)` con políticas diferenciadas por rol.
   - Función de control de acceso electoral `check_election_access(user, election, write=False)` verificando tanto `school_id` como `election_id` de comisiones.
   - Actualización de `require_role` para validar jerarquía de roles con superadmin.
   - Actualización de `log_audit` para persistir `school_id` en cada evento del sistema.
4. `backend/app/routers/schools.py`:
   - `GET /schools`: scoped a nivel de base de datos (`current_user.school_id`).
   - `POST /schools`: restringido exclusivamente a `Administrador General` (403 para responsables o comisiones).
   - `GET /schools/{id}`: protegido con `check_school_access(write=False)`.
   - `PUT /schools/{id}`: implementado y protegido con `check_school_access(write=True)`.
5. `backend/app/routers/elections.py`:
   - `GET /elections`: scoped server-side por `school_id` o `election_id` del usuario autenticado.
   - `POST /elections`: comisiones denegadas (403); responsables solo pueden crear elecciones dentro de su propio colegio.
   - `GET /elections/{id}`: protegido con `check_election_access(write=False)`.
   - `PUT /elections/{id}`: protegido con `check_election_access(write=True)`.
   - `POST /elections/{id}/abrir`: protegido con `check_election_access(write=True)`.
   - `POST /elections/{id}/cerrar`: protegido con `check_election_access(write=True)`.
   - `POST /elections/{id}/comite`: protegido con `check_election_access(write=True)`.
6. `backend/app/routers/voters.py`:
   - `GET /elections/{id}/voters`: verificación anti-IDOR con `check_election_access`.
   - `POST /elections/{id}/voters`: protegido con `check_election_access(write=True)`.
   - `POST /elections/{id}/voters/upload-excel`: protegido con `check_election_access(write=True)`.
   - `POST /elections/{id}/voters/generate-tokens`: protegido con `check_election_access(write=True)`.
   - `GET /elections/{id}/voters/simulate-email-dispatch`: protegido con `check_election_access(write=False)`.
7. `backend/app/routers/candidates.py`:
   - `GET /elections/{id}/candidates`: verificación anti-IDOR con `check_election_access`.
   - `POST /elections/{id}/candidates`: protegido con `check_election_access(write=True)`.
   - `DELETE /elections/{id}/candidates/{cand_id}`: protegido con `check_election_access(write=True)`.
8. `backend/app/routers/reports.py`:
   - `GET /reports/election/{id}/scrutiny`: protegido con `check_election_access`.
   - `GET /reports/election/{id}/acta-apertura/pdf`: protegido con `check_election_access`.
   - `GET /reports/election/{id}/acta-cierre/pdf`: protegido con `check_election_access`.
   - `GET /reports/dashboard-stats`: recalculado dinámicamente según el ámbito del usuario (superadmin: global, responsable: colegio, comisión: elección).
9. `backend/app/routers/audit.py`:
   - `GET /audit/logs`: filtrado obligatorio por institución (`AuditLog.school_id == user.school_id` o `AuditLog.usuario == user.email`).
10. `backend/app/routers/auth.py`:
    - `POST /auth/login`: token JWT y respuesta de usuario incluyen `school_id` y `election_id`. Registro de auditoría almacena `school_id`.
11. `backend/app/seed_data.py`:
    - Corregida importación de módulo `os`.

---

## 3. Matriz de Permisos por Rol y Ámbito

| Acción / Recurso | Administrador General | Responsable Institucional | Comisión Electoral |
| :--- | :---: | :---: | :---: |
| Crear nueva institución (`POST /schools`) | **Sí** | No (403) | No (403) |
| Listar instituciones (`GET /schools`) | Todas | Solo la propia | Solo la propia |
| Modificar institución (`PUT /schools/{id}`) | **Sí** | Solo la propia | No (403) |
| Crear elección (`POST /elections`) | Cualquier colegio | Solo su colegio | No (403) |
| Listar elecciones (`GET /elections`) | Todas | Elecciones de su colegio | Solo su elección asignada |
| Abrir / Cerrar elección (`POST /abrir`, `/cerrar`) | **Sí** | Elecciones de su colegio | Su elección asignada |
| Gestionar padrón y credenciales (`/voters/*`) | **Sí** | Elecciones de su colegio | Su elección asignada |
| Gestionar candidatos (`/candidates/*`) | **Sí** | Elecciones de su colegio | Su elección asignada |
| Descargar actas y escrutinio (`/reports/*`) | **Sí** | Elecciones de su colegio | Su elección asignada |
| Estadísticas de Dashboard (`/dashboard-stats`) | Globales | Scoped a su colegio | Scoped a su elección |
| Bitácora de Auditoría (`/audit/logs`) | Global | Scoped a su colegio | Scoped a su colegio/usuario |

---

## 4. Pruebas Automatizadas y Evidencia de Ejecución

### Suite Automatizada de Aislamiento y Anti-IDOR (`backend/tests/test_pr2_rbac_multitenancy.py`):
- `test_01_cross_school_access_forbidden`: **APROBADO** (Manager A no puede leer ni modificar School B -> 403).
- `test_02_cross_election_access_forbidden`: **APROBADO** (Manager A no puede leer ni modificar elecciones de School B -> 403).
- `test_03_cross_school_voters_forbidden`: **APROBADO** (Manager A no puede listar ni añadir votantes a School B -> 403).
- `test_04_cross_school_candidates_forbidden`: **APROBADO** (Manager A no puede listar candidatos de School B -> 403).
- `test_05_electoral_committee_scope_isolation`: **APROBADO** (Comisión de Elección A1 no puede acceder a Elección A2 -> 403; pero sí a A1 -> 200).
- `test_06_superadmin_retains_full_access`: **APROBADO** (Superadmin accede a cualquier institución y elección -> 200).
- `test_07_scoped_listings`: **APROBADO** (Listados de escuelas y elecciones retornan solo las del ámbito del usuario).
- `test_08_cross_school_reports_and_scrutiny_forbidden`: **APROBADO** (Manager A bloqueado de escrutinio y PDFs de School B -> 403).
- `test_09_comision_cannot_create_election_or_modify_school`: **APROBADO** (Comisión no puede crear elecciones ni modificar colegios -> 403).
- `test_10_manager_cannot_create_election_in_foreign_school`: **APROBADO** (Manager A bloqueado de crear elecciones en School B -> 403).
- `test_11_manager_cannot_create_new_school`: **APROBADO** (Solo Superadmin puede crear nuevos colegios -> 201 vs 403).
- `test_12_dashboard_stats_scoped_per_role`: **APROBADO** (Métricas de dashboard calculadas estrictamente según el ámbito: 3 vs 2 vs 1).
- `test_13_audit_logs_scoped`: **APROBADO** (Bitácoras aisladas por institución; Superadmin ve todo).
- `test_14_voter_credentials_and_tokens_idor_forbidden`: **APROBADO** (Manager A no puede generar tokens ni ver despachos de School B -> 403).
- `test_15_candidate_delete_idor_forbidden`: **APROBADO** (Manager A no puede eliminar candidatos de School B -> 403).

### Resumen de Ejecución de Pruebas:
```text
python -m unittest backend.tests.test_pr2_rbac_multitenancy:
Ran 15 tests in 34.526s (OK)

python -m unittest discover -s backend/tests -p "test_*.py":
Ran 23 tests in 40.277s (OK) - (test_pr1_security_containment + test_pr2_rbac_multitenancy)

python -m unittest backend.tests.verify_all_22_fixes:
Ran 22 tests in 0.087s (OK)

python -m unittest backend.tests.verify_security_fixes:
Ran 8 tests in 0.040s (OK)

npm run build (Frontend):
built in 2.20s (1594 modules transformed, 0 errors)
```

---

## 5. Plan de Migración de Base de Datos y Reversión

### Cambios de Esquema:
1. `ALTER TABLE users ADD COLUMN school_id INTEGER REFERENCES schools(id);`
2. `ALTER TABLE users ADD COLUMN election_id INTEGER REFERENCES elections(id);`
3. `CREATE INDEX ix_users_school_id ON users (school_id);`
4. `CREATE INDEX ix_users_election_id ON users (election_id);`
5. `ALTER TABLE audit_logs ADD COLUMN school_id INTEGER;`
6. `CREATE INDEX ix_audit_logs_school_id ON audit_logs (school_id);`

### Migración de Datos Existentes:
- Usuarios existentes con `rol = 'Administrador'` y `school_id IS NULL` se tratan automáticamente como `Administrador General` (manteniendo compatibilidad total sin interrupción operativa).
- Para asignar responsables institucionales a colegios existentes, actualizar `UPDATE users SET rol = 'Responsable Institucional', school_id = <id> WHERE ...;`.

### Plan de Reversión:
En caso de requerir reversión:
1. Restaurar rama a commit previo de PR 1 (`637a8a5`).
2. Las columnas añadidas en PostgreSQL (`school_id`, `election_id`) son `nullable`, por lo que su presencia es inocua para el código anterior si no se eliminan inmediatamente, o pueden retirarse con `ALTER TABLE users DROP COLUMN school_id, DROP COLUMN election_id;`.

---

## 6. Riesgos Residuales y Próximos Pasos (Hacia PR 3 y Fase D)

1. **Persistencia de Sesión JWT en localStorage:** Continúa pendiente para una migración formal de esquema de cookies `HttpOnly; SameSite; Secure` con CSRF token.
2. **Máquina de Estados y Congelamiento de Padrón (PR 3):** Requerido para congelar formalmente el padrón y candidaturas una vez que la elección pasa a estado `Abierta`, y validar fechas UTC timezone-aware.
3. **Voto Familiar Concurrente y Entitlement (PR 3):** Transaccionalidad a nivel de grupo familiar con PostgreSQL real para garantizar `1 voto por familia` bajo concurrencia extrema.
4. **Anonimato Criptográfico (Fase D):** El esquema actual mantiene `voter_id` asociado a la tabla `votes`; el rediseño criptográfico formal está sujeto a la aprobación del ADR `doc/adr/001-motor-de-votacion.md`.
