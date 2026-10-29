# Diagnóstico Técnico y Auditoría de Seguridad — TheoGen Electoral

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama base:** `main`
- **Commit base:** `0b654e5883145d629f331807693a1db7c9b67134`
- **Fecha de auditoría:** 27 de Octubre de 2026
- **Rol:** Ingeniero Principal de Software & Especialista en Seguridad de Sistemas Electorales
- **Estado de la plataforma:** MVP de Demostración — **No apto para elecciones vinculantes ni oficiales**

---

## 1. Resumen Ejecutivo del Diagnóstico

Se ha realizado una inspección exhaustiva del código fuente del backend (FastAPI, SQLAlchemy, Pydantic), frontend (React, Vite, MUI), infraestructura (Docker Compose, Nginx) y pruebas automatizadas existentes.

El análisis confirma que la plataforma posee una estructura modular limpia y legible, pero presenta **vulnerabilidades críticas de severidad P0** en el manejo de credenciales de votación, secreto de resultados, autenticación de sesión, concurrencia en la regla de votación familiar y aislamiento multi-inquilino. Además, los tests preexistentes (`verify_all_22_fixes.py` y `verify_security_fixes.py`) incluían aserciones basadas en inspección de cadenas de texto y mocks estáticos que generaban una falsa sensación de seguridad.

---

## 2. Metodología de Clasificación

- **Hecho Verificado (HV):** Comportamiento vulnerable reproducido directamente en el código fuente actual o mediante ejecución de tests.
- **Riesgo Teórico (RT):** Vulnerabilidad dependiente de condiciones de despliegue, configuración de red o concurrencia no mitigada en la arquitectura actual.
- **Limitación No Evaluada (LNE):** Aspectos fuera del alcance actual o dependientes de componentes externos no disponibles (e.g., servicio de correo SMTP real).

---

## 3. Matriz de Hallazgos Detallada

### Hallazgo 01: Exposición Masiva de Tokens de Votación en API y Vistas de Administración (HV — P0)
- **Ubicación:** 
  - `backend/app/schemas.py`: líneas 123–132 (`VoterResponse.token_votacion`).
  - `backend/app/routers/voters.py`: línea 35 (`list_voters`).
  - `frontend/src/pages/ElectionDetail.jsx`: líneas 641–675.
- **Comportamiento Reproducible:**
  Al consultar `GET /api/elections/{id}/voters`, el endpoint serializa y devuelve el campo `token_votacion` en texto plano para cada uno de los electores registrados en el padrón. En el frontend de administración, la tabla de electores muestra el token completo en una celda visible, con botones para "Copiar Token" y un enlace directo "Votar con este Token" (`/votar?token=${v.token_votacion}`).
- **Impacto y Riesgo:**
  Cualquier operador, auditor o atacante con credenciales de lectura en el panel de administración puede suplantar la identidad de cualquier votante y emitir votos en su nombre sin su conocimiento, destruyendo por completo la integridad de la elección.
- **Prueba de Regresión:**
  `test_voters_list_does_not_expose_voting_tokens`: Solicitar el listado de votantes como usuario autenticado y verificar que `token_votacion` no está presente en ninguna de las respuestas JSON (`assertNotIn("token_votacion", voter_dict)` o valor `None`/omitido).

---

### Hallazgo 02: Fuga de Token de Votación sin Enmascarar en Vista Previa HTML de Correo (HV — P0)
- **Ubicación:** 
  - `backend/app/routers/voters.py`: líneas 294–333 (`simulate_email_dispatch`).
- **Comportamiento Reproducible:**
  El endpoint `GET /api/elections/{id}/voters/simulate-email-dispatch` enmascara el campo `"token": "3a8f...29de"` en el diccionario JSON (CRIT-04 previo), pero en las líneas 301 y 316 construye la variable `vote_url = f"http://localhost:5173/votar?token={token}"` e inyecta el token real sin enmascarar dentro del atributo `href` del botón HTML (`<a href="{vote_url}" ...>`).
- **Impacto y Riesgo:**
  La vista previa de despacho entregada a la interfaz web expone el token de votación sin enmascarar para los primeros 50 electores del padrón dentro del campo `preview_html`.
- **Prueba de Regresión:**
  `test_simulate_email_dispatch_does_not_leak_raw_token_in_html`: Inspeccionar la respuesta de `simulate_email_dispatch` y asegurar que el token sin enmascarar no se encuentre presente ni en `preview_html` ni en `enlace_votacion`.

---

### Hallazgo 03: Transmisión de Token de Votación y JWT en Parámetros de Consulta (Query String) (HV — P0)
- **Ubicación:** 
  - `backend/app/routers/voting.py`: línea 16 (`validate_voting_token(token: str, ...)`).
  - `backend/app/auth.py`: línea 98 (`token_query: Optional[str] = Query(None, alias="token")` en `get_current_user`).
  - `frontend/src/services/api.js`: línea 133 (`/voting/validate-token?token=...`) y líneas 153, 157 (`/reports/election/{id}/acta-.../pdf?token=...`).
  - `frontend/src/pages/PublicVote.jsx`: líneas 40, 57–60 (`searchParams.get('token')`).
- **Comportamiento Reproducible:**
  El endpoint `POST /api/voting/validate-token` recibe el token de sufragio a través de la query string (`?token=...`). Asimismo, `get_current_user` acepta el JWT administrativo en el parámetro `?token=...`, utilizado por el frontend para descargar actas PDF mediante enlaces `<a href="...">`.
- **Impacto y Riesgo:**
  Los secretos quedan expuestos en logs de acceso de servidores web (Nginx), balanceadores de carga, historial de navegación, proxies intermediarios y encabezados `Referer`.
- **Prueba de Regresión:**
  `test_query_token_rejected_in_auth_and_voting`:
  1. Realizar una petición a un endpoint administrativo pasando el JWT únicamente por query param `?token=...` y verificar que retorna `401 Unauthorized`.
  2. Verificar que `/api/voting/validate-token` rechaza la query string y exige un payload JSON estructurado en el cuerpo (`POST` con body `{"token": "..."}`).
  3. Comprobar que las descargas PDF se ejecutan mediante cabecera `Authorization: Bearer <token>`.

---

### Hallazgo 04: Fuga de Resultados y Escrutinio en Elecciones Abiertas (HV — P0)
- **Ubicación:** 
  - `backend/app/routers/reports.py`: líneas 15–90 (`get_election_scrutiny`) y líneas 126–163 (`download_acta_cierre_pdf`).
  - `backend/app/routers/candidates.py`: líneas 27–34 (`list_candidates`).
  - `frontend/src/pages/ElectionDetail.jsx`: pestaña de escrutinio.
- **Comportamiento Reproducible:**
  El endpoint `GET /api/reports/election/{id}/scrutiny` no valida el estado de la elección. Si una elección está en estado `Abierta`, cualquier usuario con acceso al panel puede invocar este endpoint y obtener el conteo exacto de votos por candidato, porcentajes acumulados y proclamación del ganador temporal. Asimismo, `download_acta_cierre_pdf` emite el acta de cierre antes del término del sufragio.
- **Impacto y Riesgo:**
  Destrucción del secreto y neutralidad del proceso electoral. La revelación parcial de resultados influye decisivamente en los electores restantes (efecto arrastre / voto estratégico).
- **Prueba de Regresión:**
  `test_scrutiny_and_acta_blocked_when_election_open`: Enviar peticiones a `/reports/election/{id}/scrutiny` y `/reports/election/{id}/acta-cierre/pdf` para una elección en estado `Abierta` y verificar que el servidor responde con `403 Forbidden` o `409 Conflict`.

---

### Hallazgo 05: Filtración de Identidad de Votante Familiar en Validación de Credencial (HV — P1)
- **Ubicación:** 
  - `backend/app/routers/voting.py`: líneas 67–70.
- **Comportamiento Reproducible:**
  Al validar un token perteneciente a una familia donde otro integrante ya votó, el servidor responde:
  `"El representante familiar ({family_vote.nombre}) ya emitió el sufragio correspondiente al grupo {voter.familia_id}."`
- **Impacto y Riesgo:**
  Revela a terceros qué miembro específico de la familia emitió el voto, vulnerando la privacidad intra-familiar del sufragio.
- **Prueba de Regresión:**
  `test_family_validation_does_not_reveal_voter_identity`: Al validar una credencial familiar cuyo cupo ya fue utilizado, el mensaje devuelto debe ser genérico: *"Ya se ha registrado un sufragio para este grupo familiar."*, sin incluir nombres ni datos identificatorios.

---

### Hallazgo 06: Validación de Complejidad de Contraseña en el Esquema de Login (HV — P1)
- **Ubicación:** 
  - `backend/app/schemas.py`: líneas 7–21 (`UserLogin.validate_password_strength`).
- **Comportamiento Reproducible:**
  El esquema Pydantic `UserLogin` contiene un validador `@field_validator("password")` que exige longitud >= 8 caracteres, al menos una letra y al menos un número.
- **Impacto y Riesgo:**
  Impide que usuarios existentes con contraseñas históricas o generadas previamente inicien sesión si no cumplen la regex, provocando denegación de servicio no planificada. La validación de complejidad debe residir exclusivamente en la creación y cambio de contraseña (`UserCreate`, restablecimiento).
- **Prueba de Regresión:**
  `test_user_login_schema_accepts_any_string`: Instanciar `UserLogin(email="user@test.cl", password="simple")` y verificar que no genera `ValidationError`.

---

### Hallazgo 07: Desalineación Crítica de Rutas en Configuración Nginx de Producción (HV — P0)
- **Ubicación:** 
  - `doc/templates/nginx-ssl.conf`: líneas 80–97.
- **Comportamiento Reproducible:**
  Las directivas de limitación de tasa apuntan a:
  - `location /api/voting/vote`: ruta inexistente en FastAPI (la ruta real es `/api/voting/submit`).
  - `location /api/auth/token`: ruta inexistente en FastAPI (la ruta real es `/api/auth/login`).
  - No existe directiva específica de rate limiting para `/api/voting/validate-token`.
- **Impacto y Riesgo:**
  En producción detrás de Nginx, las peticiones a `/api/voting/submit` caen en el bloque genérico `/api/` (20 req/s con ráfaga de 20), sin la protección estricta requerida para votación. Peor aún, los ataques de fuerza bruta contra `/api/auth/login` y `/api/voting/validate-token` no están contenidos por el proxy.
- **Prueba de Regresión:**
  `test_nginx_config_syntax_and_endpoints`: Validar sintaxis y constatar que las ubicaciones en `nginx-ssl.conf` coinciden con los endpoints vigentes del backend (`/api/voting/submit`, `/api/voting/validate-token`, `/api/auth/login`).

---

### Hallazgo 08: Datos de Demostración Sembrados Indiscriminadamente en Arranque y Exposición de Secretos en Logs (HV — P1)
- **Ubicación:** 
  - `backend/main.py`: líneas 45–51 (`lifespan`).
  - `backend/app/seed_data.py`: líneas 41–48 (`logger.warning("Admin: admin@theogen.cl / %s", admin_password)`).
- **Comportamiento Reproducible:**
  En cada arranque de la aplicación FastAPI, se ejecuta `seed_initial_data(db)` incondicionalmente, incluso si `ENVIRONMENT=production`. Además, `seed_data.py` imprime las contraseñas generadas en el log del sistema mediante `logger.warning`.
- **Impacto y Riesgo:**
  Posible inyección de datos de demo en bases de datos productivas y persistencia de contraseñas administrativas en archivos de registro.
- **Prueba de Regresión:**
  `test_production_startup_does_not_seed_demo_data`: Configurar `ENVIRONMENT=production` y verificar que el arranque no ejecuta seed de datos ni emite contraseñas a los logs a menos que exista una bandera explícita `SEED_DEMO_DATA=true`.

---

### Hallazgo 09: Condición de Carrera en Voto Familiar Concurrente (HV — P0)
- **Ubicación:** 
  - `backend/app/routers/voting.py`: líneas 118–144 (`submit_vote`).
- **Comportamiento Reproducible:**
  La sentencia `SELECT FOR UPDATE` se realiza sobre la fila `Voter` correspondiente al token enviado (`Voter.token_votacion == token_clean`). En el caso de "Un voto por familia", diferentes miembros de la familia poseen filas `Voter` distintas. Si dos integrantes envían su voto simultáneamente en hilos concurrentes, ambos adquieren el lock sobre su propia fila `Voter`, ejecutan la consulta `family_vote = db.query(Voter)...` antes de que el otro haya confirmado (`commit`), y ambos votos son insertados en la tabla `Vote`.
- **Impacto y Riesgo:**
  Violación de la regla "Un voto por familia", duplicación de sufragios familiares en elecciones disputadas.
- **Prueba de Regresión:**
  `test_concurrent_family_voting_pg`: Ejecución de 20 a 50 peticiones concurrentes simultáneas sobre PostgreSQL real para dos miembros de la misma familia, validando que exactamente una sea aceptada y el resto rechazada con error de unicidad/transaccional.

---

### Hallazgo 10: Ausencia de Aislamiento Multi-Inquilino (Multi-Tenant IDOR) (HV — P0)
- **Ubicación:** 
  - `backend/app/models.py`: modelo `User` sin relación con `School`.
  - Routers `schools.py`, `elections.py`, `voters.py`, `candidates.py`, `reports.py`, `audit.py`.
- **Comportamiento Reproducible:**
  Un usuario con rol "Comisión Electoral" o "Administrador" puede interactuar con cualquier `election_id` o `school_id` simplemente alterando el parámetro en la URL. No existe verificación de pertenencia del usuario a la institución ni a la comisión electoral de esa elección específica.
- **Impacto y Riesgo:**
  Acceso no autorizado, manipulación y visualización de padrones y procesos electorales de otros colegios (Insecure Direct Object Reference).

---

### Hallazgo 11: Falta de Pruebas Funcionales Reales en la Suite Previa (HV — P1)
- **Ubicación:** 
  - `backend/tests/verify_all_22_fixes.py` y `backend/tests/verify_security_fixes.py`.
- **Comportamiento Reproducible:**
  Varios tests verificaban seguridad buscando cadenas en el código fuente (e.g. `self.assertIn("with_for_update()", code)` en el test 10) o simulando variables aisladas en memoria sin levantar la aplicación ni ejercitar las rutas HTTP con clientes de prueba.
- **Impacto y Riesgo:**
  Falsos positivos: los tests reportaban 30/30 pruebas exitosas mientras las vulnerabilidades descritas en los hallazgos 01 al 10 estaban plenamente activas en el código fuente.

---

## 4. Estado de Servicios y Dependencias en el Entorno Local

- **Python:** 3.11.7 (en `backend/venv`).
- **Node.js:** v22.16.0 (frontend dependencias instaladas en `frontend/node_modules`).
- **Docker:** Versión 29.1.2 instalada; servicio Docker Desktop detenido en el momento de la revisión.
- **PostgreSQL:**
  - Instancias de Windows en ejecución: `postgresql-x64-16` (puerto 5432) y `postgresql-x64-17` (puerto 5433).
  - Estado: Servicio local activo; autenticación configurada a nivel de sistema.
- **Base de datos de desarrollo por defecto:** SQLite local (`theogen_electoral.db`) para ejecución desacoplada; soporte psycopg2 instalado para PostgreSQL.

---

## 5. Plan de Ejecución por Fases y Pull Requests

1. **PR 1 (Fase Actual): Contención Inmediata de Seguridad**
   - Eliminación de tokens de votación en `VoterResponse`, listados de padrón y vista previa de correos.
   - Migración de `validate-token` a body JSON y eliminación de tokens en URLs/query strings.
   - Retiro de `token_query` en `get_current_user` y adaptación de descargas PDF con `Authorization` header.
   - Desactivación de validación de complejidad de contraseña en login (`UserLogin`).
   - Bloqueo en backend de escrutinio y acta definitiva cuando la elección esté `Abierta` (403 Forbidden).
   - Ocultamiento de la identidad del votante familiar en mensajes de validación.
   - Corrección de rutas y rate limiting en `doc/templates/nginx-ssl.conf`.
   - Restricción de seed de demostración para que no arranque en producción ni imprima contraseñas en logs.
   - Creación de suite de pruebas funcionales automatizadas con `TestClient` (FastAPI + HTTPX) que verifiquen el cierre de estos vectores.

2. **PR 2: Aislamiento por Organización y Control de Acceso (RBAC / Anti-IDOR)**
   - Modelo de membresía explícita de usuarios por institución (`school_id`).
   - Matriz de permisos estricta: Administrador General, Responsable Institucional y Comisión Electoral.
   - Verificación de ámbito en todos los routers y endpoints.

3. **PR 3: Máquina de Estados, Congelamiento de Padrón y Voto Familiar Transaccional**
   - Transiciones de estado estrictas y auditadas.
   - Congelamiento inmutable de padrón y candidatos tras la apertura.
   - Entidad de derecho a sufragio (entitlement) y bloqueo de concurrencia a nivel BD para regla familiar.
   - Tratamiento de empates y recálculo de denominadores de participación.

4. **PR 4: Migraciones Alembic, Auditoría Robusta y Calidad de Operación**
   - Integración de Alembic para evolución de esquema.
   - Auditoría transaccional consistente y protección de datos personales.
   - Pipeline de integración continua (CI) con GitHub Actions.

5. **Fase D (Documento Independiente): ADR de Arquitectura del Motor Criptográfico**
   - Evaluación técnica formal de integración con Belenios autohospedado vs. diseño de motor propio con pruebas de conocimiento cero (ZKP) y urnas verificables.
   - **Prohibición estricta:** No se modificará el núcleo criptográfico ni se declarará vinculante sin aprobación previa del ADR.
