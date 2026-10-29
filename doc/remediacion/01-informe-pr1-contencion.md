# Informe de Cierre — PR 1: Contención Inmediata de Seguridad

- **Repositorio:** `OsvaldoVegaOses/_Electoral`
- **Rama:** `fix/pr1-security-containment`
- **Base:** `main` (`0b654e5883145d629f331807693a1db7c9b67134`)
- **Fecha:** 27 de Octubre de 2026
- **Estado de la fase:** Completada y Verificada con Pruebas Automatizadas

---

## 1. Identificación y Descripción de Riesgos Mitigados (P0 y P1)

| ID | Gravedad | Descripción del Riesgo | Impacto Mitigado |
| :--- | :--- | :--- | :--- |
| **VULN-01** | **P0** | Exposición de `token_votacion` en serialización de padrón (`GET /elections/{id}/voters`) y en tabla de administración con enlaces directos de sufragio. | Eliminación del riesgo de suplantación masiva de electores por operadores o auditores con acceso al panel. |
| **VULN-02** | **P0** | Fuga de token sin enmascarar dentro del atributo `href` de `preview_html` en el endpoint `simulate-email-dispatch`. | Eliminación de fuga de credenciales en vistas previas de despacho de correo. |
| **VULN-03** | **P0** | Recepción de tokens de votación mediante parámetros de consulta URL (`POST /voting/validate-token?token=...`). | Supresión de credenciales en registros de acceso, proxies, historial y cabeceras `Referer`. |
| **VULN-04** | **P0** | Aceptación de JWT administrativo por query string (`?token=JWT`) para descarga de actas PDF. | Eliminación de tokens de sesión expuestos en URLs; migración a cabecera `Authorization: Bearer`. |
| **VULN-05** | **P1** | Regla de complejidad de contraseñas aplicada en esquema de autenticación `UserLogin`. | Prevención de denegación de servicio para cuentas existentes con credenciales históricas. |
| **VULN-06** | **P0** | Exposición en tiempo real de escrutinio detallado, conteo por lista y acta de cierre en elecciones en estado `Abierta`. | Garantía del secreto del voto y prevención de manipulación o voto estratégico durante el sufragio. |
| **VULN-07** | **P1** | Fuga del nombre del integrante familiar que ya emitió sufragio al validar credenciales del mismo grupo. | Protección de la privacidad intra-familiar en procesos con regla "Un voto por familia". |
| **VULN-08** | **P0** | Ausencia de protección contra fuerza bruta y enumeración en validación de tokens y emisión de sufragios. | Implementación de rate limiting estricto tanto en servidor FastAPI como en plantilla de Nginx. |
| **VULN-09** | **P1** | Arranque incondicional de seed de demostración en producción y registro de contraseñas administrativas en logs. | Prevención de inyección de datos de demo en producción y supresión de credenciales en logs de sistema. |
| **VULN-10** | **P0** | Desalineación de endpoints en configuración Nginx (`/api/voting/vote` y `/api/auth/token`). | Alineación a rutas reales (`/api/voting/submit`, `/api/voting/validate-token`, `/api/auth/login`). |

---

## 2. Archivos y Endpoints Modificados

### Backend:
1. `backend/app/schemas.py`:
   - Removido `token_votacion` del esquema de salida `VoterResponse`.
   - Creado esquema `TokenValidateRequest` para validar entrada en cuerpo JSON (`token`).
   - Retirada la validación de complejidad en `UserLogin`, preservándola en `UserCreate`.
2. `backend/app/auth.py`:
   - Retirado `token_query` en `get_current_user` (solo se admite `Authorization: Bearer`).
   - Creada función auxiliar `get_client_ip` compatible con proxies inversos (`X-Forwarded-For`).
3. `backend/app/routers/voting.py`:
   - `POST /voting/validate-token`: ahora recibe `payload: TokenValidateRequest` y aplica `check_rate_limit`.
   - Modificado mensaje de regla familiar para no revelar el nombre de la persona que sufragó.
   - `POST /voting/submit`: integrado con `check_rate_limit` y limpieza de intentos tras éxito.
4. `backend/app/routers/voters.py`:
   - `GET /elections/{id}/voters/simulate-email-dispatch`: enlace genérico seguro a `/votar` sin parámetros de credenciales en `preview_html` ni en `enlace_votacion`.
5. `backend/app/routers/reports.py`:
   - `GET /reports/election/{id}/scrutiny`: bloqueado con `403 Forbidden` si la elección no está `Cerrada` o `Finalizada`.
   - Cálculo corregido del padrón electoral para regla "Un voto por familia" (unidades electorales únicas).
   - Manejo estricto de empates y elecciones sin sufragios (sin ganador ficticio automático).
   - `GET /reports/election/{id}/acta-cierre/pdf`: bloqueado con `403 Forbidden` mientras esté `Abierta`.
   - Sanitización ASCII en nombres de archivo para cabeceras HTTP `Content-Disposition`.
6. `backend/app/routers/candidates.py`:
   - `GET /elections/{id}/candidates`: `votos_count` oculto (`0`) salvo que la elección esté formalmente `Cerrada` o `Finalizada`.
7. `backend/app/seed_data.py`:
   - Eliminado el registro de contraseñas en texto claro en logs (`logger.warning`).
   - Eliminada la afirmación de proceso "oficial y vinculante" en la descripción de elecciones demo.
8. `backend/main.py`:
   - `seed_initial_data` condicionado a `ENVIRONMENT in ["development", "test"]` y opt-in explícito con `SEED_DEMO_DATA=true`. Omitido incondicionalmente en `production`.

### Frontend:
1. `frontend/src/services/api.js`:
   - `votingService.validateToken`: envía payload JSON `{ token }` por `POST /voting/validate-token`.
   - `reportService.downloadActaAperturaPdf` y `downloadActaCierrePdf`: descargas autenticadas vía Axios con cabecera `Authorization` y blobs en memoria (eliminando `?token=JWT`).
2. `frontend/src/pages/PublicVote.jsx`:
   - Sanitización inmediata de la barra de direcciones (`replaceState`) para suprimir tokens de la URL si se llega por enlace directo.
3. `frontend/src/pages/ElectionDetail.jsx`:
   - Padrón: eliminada la columna de `token_votacion` en texto plano y los botones de suplantación directa "Votar con este Token".
   - Filtro de búsqueda ajustado para usar `familia_id` en lugar del token.
   - Pestaña de Escrutinio: tarjeta informativa de protección de resultados si la elección está abierta; escrutinio detallado solo visible tras el cierre formal.
   - Botón de Acta de Cierre: protegido y descargado vía Blob autenticado.
   - `loadAllData`: no solicita escrutinio detallado si la elección no está cerrada, evitando errores 403.

### Infraestructura:
1. `doc/templates/nginx-ssl.conf`:
   - Ubicaciones corregidas: `/api/voting/submit`, `/api/voting/validate-token` y `/api/auth/login` con zonas de rate limiting independientes.

---

## 3. Pruebas Automatizadas y Evidencia de Ejecución

### Suite de Pruebas de Contención de Seguridad (`backend/tests/test_pr1_security_containment.py`):
- `test_01_voters_list_does_not_expose_voting_tokens`: **APROBADO** (Ningún votante expone `token_votacion`).
- `test_02_simulate_email_dispatch_does_not_leak_raw_tokens_in_html`: **APROBADO** (`preview_html` y enlaces no contienen tokens crudos).
- `test_03_voting_token_in_query_rejected_must_be_in_body`: **APROBADO** (Token por query string no devuelve 200; token por body JSON aceptado).
- `test_04_auth_jwt_in_query_string_rejected`: **APROBADO** (JWT en query string rechazado con `401 Unauthorized`).
- `test_05_user_login_schema_accepts_any_password_string`: **APROBADO** (`UserLogin` no bloquea contraseñas históricas).
- `test_06_scrutiny_and_acta_cierre_blocked_when_election_is_open`: **APROBADO** (Retorna `403 Forbidden` mientras la elección esté abierta).
- `test_07_family_validation_does_not_reveal_voter_name`: **APROBADO** (Mensaje familiar anónimo sin nombres personales).
- `test_08_rate_limiting_on_voting_validate_token`: **APROBADO** (Respuestas `429 Too Many Requests` tras intentos fallidos excesivos).

### Resultado Global de Pruebas Backend:
```text
pytest backend/tests/test_pr1_security_containment.py:
8 passed, 9 warnings in 8.43s (100% OK)

unittest discover (verify_all_22_fixes.py + verify_security_fixes.py):
Ran 30 tests in 0.303s (OK)
```

### Resultado de Verificación Frontend:
```text
oxlint: 0 errors
vite build: ✓ built in 5.58s (dist/assets/index-Cz_vOk3C.js)
```

---

## 4. Migraciones de Base de Datos y Reversibilidad

- **Cambios en Esquema de BD en esta fase:** Ninguno. Se mantuvieron intactos los modelos SQLAlchemy existentes para asegurar retrocompatibilidad con bases de datos operativas y no ejecutar alteraciones destructivas de datos.
- **Plan de Reversión:** Las modificaciones están aisladas en la capa de serialización Pydantic, dependencias de FastAPI y componentes de React. En caso de requerir reversión, basta con revertir los commits de la rama `fix/pr1-security-containment`.

---

## 5. Riesgos Residuales y Tareas para Siguientes Fases

1. **Aislamiento Multi-Inquilino (Fase PR 2 - Prioridad Inmediata):**
   - Actualmente `User` no posee asociación estricta a `School` ni restricciones de ámbito por elección. Un usuario autenticado aún podría interactuar con recursos de otra institución mediante manipulación de IDs (IDOR).
2. **Concurrencia en Voto Familiar (Fase PR 3):**
   - La regla "Un voto por familia" requiere una entidad de derecho a sufragio compartida (entitlement) con unicidad a nivel de motor de base de datos transaccional PostgreSQL para evitar carreras en milisegundos.
3. **Persistencia de Sesión Administrativa (PR 2 / PR 4):**
   - El token JWT administrativo aún se almacena en `localStorage` en el cliente. Se recomienda migrar a cookies `HttpOnly; Secure; SameSite` con protección CSRF.
4. **Núcleo Criptográfico Electoral (Fase D):**
   - La plataforma continúa siendo un MVP no apto para elecciones vinculantes. La tabla `Vote` mantiene asociación técnica con el votante y el candidato. El diseño del motor con secreto verificable se presentará en el ADR formal de la Fase D para aprobación previa.
