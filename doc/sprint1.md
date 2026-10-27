Mandato de remediación para agente IA — TheoGen Electoral
Repositorio: https://github.com/OsvaldoVegaOses/_Electoral
Rama base: main
Commit observado en la revisión: 0b654e5883145d629f331807693a1db7c9b67134
Fecha de revisión: 27-10-2026
Alcance: endurecimiento del MVP y propuesta de arquitectura de votación segura; no habilitar elecciones vinculantes.
1. Rol y objetivo
Actúa como ingeniero/a principal de backend y frontend, especialista en seguridad de aplicaciones, bases de datos transaccionales, pruebas automatizadas y arquitectura de sistemas de votación. Trabaja sobre el repositorio real; verifica el estado de main y no supongas que el commit anterior sigue siendo HEAD. Conserva React/Vite/MUI, FastAPI/SQLAlchemy y PostgreSQL, así como las funcionalidades visibles, salvo cuando representen un riesgo demostrado. No reemplaces el producto ni agregues microservicios sin justificación.

Tu trabajo es corregir los defectos de seguridad y de consistencia que no requieren inventar un protocolo criptográfico electoral, demostrarlos con pruebas que ejerciten el sistema y entregar una decisión de arquitectura documentada para el núcleo electoral. No se autoriza poner el servicio en producción, desplegarlo, usar padrones reales ni declarar seguro o anónimo el sufragio.
2. Forma de trabajo obligatoria
1. Obtén el SHA exacto de HEAD, árbol de archivos, dependencias y estado de git; inspecciona la documentación y los tests. Abre fix/electoral-hardening desde main o separa por PR independientes si resulta más seguro. No sobrescribas cambios locales ni secretos.
2. Redacta doc/remediacion/00-diagnostico.md con evidencia por hallazgo: ruta, líneas o función, comportamiento reproducible, gravedad, riesgo y prueba de regresión. Distingue hechos verificados, riesgos teóricos y limitaciones no evaluadas.
3. Crea tests que fallen frente al comportamiento vulnerable antes de corregir, cuando sea posible. Ejecuta la suite existente como línea base y registra sus resultados. No confundas pruebas de búsqueda de cadenas de código con pruebas funcionales.
4. Implementa cambios pequeños y revisables; evita commits masivos. Entrega una PR o conjunto de PR con descripción de cambios, impactos de API/BD, migraciones, forma de probar y limitaciones remanentes.
5. No declares aprobado un control cuya prueba no se ejecutó. Si Docker/PostgreSQL/browser no está disponible, indícalo y marca explícitamente la prueba como pendiente.
6. No ejecutes operaciones destructivas, migres datos reales ni alteres despliegues productivos sin autorización. Si una migración puede comprometer votos o datos existentes, detente y documenta plan de respaldo, transición y recuperación.
3. Fase A — Contención inmediata, implementable
A1. Credenciales de voto y de sesión — P0
Archivos iniciales: backend/app/schemas.py, backend/app/models.py, backend/app/routers/voters.py, backend/app/routers/voting.py, backend/app/auth.py, frontend/src/services/api.js, frontend/src/pages/PublicVote.jsx, frontend/src/context/AuthContext.jsx.
- Elimina token_votacion de toda respuesta normal de padrón. Revisa todas las serializaciones y vistas de administración; no basta con enmascarar el campo token si preview_html o enlace_votacion contiene la credencial.
- Suprime tokens de votación en URLs, parámetros de consulta, logs, respuestas de error y vistas previas. Actualmente votingService.validateToken construye POST /voting/validate-token?token=...; cámbialo a entrada validada en el cuerpo de la petición, sin alterar indebidamente los nombres de las rutas.
- Para un MVP sin entrega segura implementada, muestra un enlace genérico a /votar y un procedimiento de entrega de credencial separado. No simules un despacho efectivo como si existiera. Diseña almacenamiento de credenciales mediante derivación/hash resistente y canje controlado, sin volver a exponer el secreto al operador. Documenta la transición desde tokens existentes.
- En get_current_user, retira token_query. Modifica las descargas PDF del frontend para usar una solicitud autenticada con cabecera Authorization y descargar el Blob, no ?token=JWT. Elimina el uso de tokens JWT en la URL por completo.
- No presentes una contraseña de acceso como un requisito de complejidad en el login que impida comprobar contraseñas existentes: deja controles robustos en alta/restablecimiento, no bloquees arbitrariamente autenticaciones históricas.
- Revisa la persistencia del JWT administrativo en localStorage; propone e implementa un esquema de sesión más resistente a XSS (por ejemplo, cookie HttpOnly; Secure; SameSite y protección CSRF acorde a la arquitectura), con tests de login, logout y expiración. Si esta migración exige una PR separada, documenta la separación y no la declares completada.
- Evita revelar qué miembro de una familia votó al validar otra credencial. Devuelve únicamente estado de habilitación y mensajes mínimos necesarios.
- Incorpora protección contra fuerza bruta/enumeración para validación de credenciales y envío de voto, combinando límites en proxy y servidor según despliegue; evita un contador solo en memoria como única defensa si hay varias instancias.
Pruebas de aceptación: ningún endpoint de padrón, simulación o acta devuelve credenciales utilizables; grep de rutas y logs más pruebas HTTP; JWT en query rechazado; el votante legítimo todavía puede acceder sin exposición por URL; solicitudes inválidas y repetidas quedan limitadas.
A2. Protección de resultados — P0
Archivos: backend/app/routers/reports.py, backend/app/routers/candidates.py, frontend/src/pages/ElectionDetail.jsx, frontend/src/pages/Dashboard.jsx.
- Bloquea en el backend el escrutinio por candidato/lista y el acta definitiva cuando el estado no sea Cerrada o Finalizada. Ninguna consulta, PDF, listado de candidatos ni respuesta JSON debe filtrar resultados desagregados mientras está Abierta.
- Durante la votación solo permite indicadores agregados de participación a usuarios autorizados, sin revelar preferencias.
- Tratar empates, elecciones sin votos y opciones blanco/nulo sin proclamar ficticiamente un ganador. Registra la regla aplicada; no presupongas una regla jurídica universal.
- Corrige los cálculos de denominadores: cuando rige Un voto por familia, la unidad habilitada es el grupo familiar, no necesariamente el número de personas inscritas.
Pruebas: antes del cierre todo endpoint de resultados detallados retorna 403/409 y ninguna fuga lateral; tras el cierre retorna totales correctos; empate y cero votos no generan ganador automático; regla familiar reporta porcentaje consistente.
A3. Aislamiento por organización y autorización — P0
Archivos: backend/app/auth.py, backend/app/models.py, routers schools, elections, voters, candidates, reports, audit, y schemas.
- Implementa membresía explícita de usuarios a instituciones y roles por ámbito, con política de mínimo privilegio y denegación por defecto. El rol global Administrador no debe inferirse para todos los usuarios.
- Aplica controles del lado servidor a cada lectura/escritura y a exportaciones, documentos, estadísticas y auditoría. El filtrado en React no cuenta como medida de seguridad.
- Separa Administrador General, responsable institucional y Comisión Electoral, especificando matriz de permisos y acciones reservadas. Para una comisión, aplica también ámbito de elección donde corresponda.
- Impide que cambiar un school_id o election_id de la URL permita acceder al padrón, credenciales, informes o resultados de otra institución (IDOR).
Pruebas: usuario de colegio A no consulta ni modifica B; comisión de elección X no gestiona Y; rol sin permisos falla en backend incluso mediante llamadas API directas; administrador designado conserva las atribuciones documentadas.
A4. Voto único transaccional y regla familiar — P0
Archivos: backend/app/models.py, backend/app/routers/voting.py, backend/app/routers/voters.py y nueva migración.
- Introduce una entidad estable de derecho a sufragio / unidad electoral (entitlement) con clave única por elección: persona o familia conforme a la regla; todos los miembros del mismo grupo familiar deben competir por el mismo derecho, no por filas Voter diferentes.
- Usa transacciones PostgreSQL, bloqueos adecuados sobre el mismo derecho y restricciones/índices únicos de BD; no dependas únicamente de SELECT FOR UPDATE sobre el votante ni de comprobaciones previas en memoria. Bloquea también las operaciones de cierre vs emisión simultánea de sufragio con orden consistente de locks.
- Normaliza RUT y establece unicidad a nivel BD (election_id, rut_normalizado). No aceptes una elección familiar con derechos ambiguos: exige familia_id válido o marca las filas como pendientes de saneamiento antes de abrir la elección.
- Una reejecución/reintento de la operación de voto debe tener semántica segura (a lo sumo un sufragio aceptado por derecho electoral). Establece el tratamiento de reintentos de red sin dar acceso al sentido del voto.
- No consideres resuelto el secreto del voto: el modelo actual guarda Vote.voter_id y candidate_id juntos. Esta fase evita duplicados; el rediseño de anonimato queda bloqueado por la decisión de arquitectura de la fase D.
Pruebas: 20–100 solicitudes verdaderamente concurrentes usando PostgreSQL con el mismo token y con dos tokens de una misma familia: exactamente una se acepta; ninguna otra cuenta como voto; cierre/emisión concurrentes dejan estado consistente; tasa de participación correcta.
4. Fase B — Integridad del proceso electoral y datos
B1. Máquina de estados
Archivos: backend/app/routers/elections.py, backend/app/routers/candidates.py, backend/app/routers/voters.py, schemas y frontend.
- Impide cambiar estado por el PUT /elections/{id} general. Mantén transiciones explícitas auditadas (abrir, cerrar, finalizar), validadas atómicamente; si se introduce suspensión/reanudación, documenta su semántica antes de codificar.
- En Borrador: permitir preparar instituciones, comisiones, padrón, regla y candidaturas. Para abrir: validar padrón íntegro, unidad electoral y fechas coherentes; generar instantánea/versionado o hash de configuración aprobada. En Abierta: congelar lista de votantes, candidatos, comisiones y reglas; permitir solo sufragar y consultar participación agregada. En Cerrada: rechazar nuevos votos; habilitar escrutinio.
- Usar hora de servidor como autoridad, almacenar UTC con tipo timezone-aware en PostgreSQL y comunicar horas locales correctamente. fecha_inicio y fecha_fin deben aplicarse al votar incluso si estado estuviera incorrectamente Abierta; evitar ambigüedad entre calendario programado y acción manual de apertura.
- Prohibir modificación del padrón y de candidaturas después de apertura, incluidos endpoints individuales y masivos. Regla de cierre, finalización y reapertura se define explícitamente; no permitir cambiar estado por atajos.
Pruebas: todas las transiciones inválidas rechazadas; modificación tras apertura rechazada; votos fuera de ventana bloqueados; carreras cerrar/submit seguras.
B2. Datos sensibles, auditoría y migraciones
- Incorpora Alembic y migraciones reversibles cuando sea factible. En producción, sustituye Base.metadata.create_all como mecanismo de evolución del esquema por migraciones controladas; conserva instalaciones existentes con plan de actualización y respaldo.
- Corrige backend/main.py: datos demo solo con opt-in explícito y ENVIRONMENT=development/test; jamás al arrancar producción. Crea provisionamiento seguro de administrador sin imprimir contraseñas en logs. Elimina del seed afirmaciones de proceso 'oficial y vinculante'.
- Minimiza registro de RUT, correo, tokens, hash del voto y datos que permitan correlacionar identidad/elección. Revisa acceso, cifrado/segregación, política de retención, eliminación y respaldos con datos personales.
- Registra eventos críticos de negocio de modo consistente con su transacción o mediante outbox; no dejes un voto confirmado con auditoría obligatoria fallida y viceversa.
- No llames 'bitácora inmutable' a una tabla convencional. Diseña almacenamiento append-only y evidencia verificable de alteración con anclaje externo/controles independientes si se requiere una garantía fuerte; un encadenamiento hash local sin anclaje no equivale a inmutabilidad.
- Revisa importación CSV/Excel: tamaño máximo por lectura incremental, esquema y formatos válidos, preservar RUT como cadena, reporte de filas con error, consistencia de correo, soporte real de .xls (o retirar esa promesa) y protección contra duplicados simultáneos. No cargues el archivo completo antes de decidir que excede el límite.
Pruebas: arranque prod limpio sin seed ni credenciales demo; migrations upgrade/downgrade en BD de ensayo; importación malformada/duplicados/10MB; auditoría coherente en fallos y reintentos; datos sensibles ausentes de logs y respuestas.
5. Fase C — Operación reproducible y calidad
C1. Infraestructura
- En doc/templates/nginx-ssl.conf, los límites especiales apuntan erróneamente a /api/voting/vote y /api/auth/token, pero las rutas reales son /api/voting/submit, /api/voting/validate-token y /api/auth/login; alinea location y proxy_pass, aplica límites adecuados a los tres endpoints y pruébalos.
- Revisa los paths, contexto del build y .env de doc/templates/docker-compose.prod.yml al usar docker compose -f doc/templates/docker-compose.prod.yml ...; asegura que funcionen desde la ruta documentada, sin exponer PostgreSQL públicamente.
- Hace configurable y restrictivo CORS en producción, valida variables y calidad de secretos al inicio, fija política de logs, healthchecks de disponibilidad y readiness de BD, backup/restauración verificados, y pruebas de fallo/corte en día de elección.
- Actualiza configuración, README, ejemplo .env y guías de producción; elimina enlaces locales file:/// que no sirven desde GitHub.
C2. Calidad y automatización
- Crea GitHub Actions (o CI equivalente) con lint frontend, build, pytest backend, integración sobre PostgreSQL, escaneo de dependencias y detección de secretos. Establece versions/locks reproducibles y actualizaciones controladas.
- Agrega tests HTTP de APIs y reglas, concurrencia transaccional, permisos multiinstitución, descarga autenticada de PDF, validación de tiempos y E2E del flujo demo desde navegador.
- Inspecciona los tests previos verify_all_22_fixes.py y verify_security_fixes.py: consérvalos si ayudan, pero reemplaza afirmaciones basadas solo en búsqueda de texto por pruebas de comportamiento.
- Realiza docker compose config, validación Nginx (nginx -t), tests pytest, npm run lint, npm run build, escaneo de dependencias y ensayo de restauración cuando el entorno lo permita. Registra comandos, resultado y versiones.
6. Fase D — Decisión sobre motor criptográfico (NO PROGRAMAR SIN APROBACIÓN)
El esquema actual asocia Vote.voter_id con Vote.candidate_id, junto con marcas temporales y una bitácora. Un HMAC calculado desde una cadena que no permite verificación independiente no constituye una prueba pública de urna íntegra; un simple hash de comprobante tampoco garantiza secreto ni verificabilidad. Eliminar voter_id no corrige automáticamente correlaciones por tiempos, tokens, logs o respaldos; tampoco anonimiza retroactivamente votos ya almacenados.

Redacta un ADR: doc/adr/001-motor-de-votacion.md, comparando:
1. Integración Belenios autohospedado: estudiar versión concreta, interfaz de integración disponible (no asumir API pública), licencia, responsabilidades de autoridad de credenciales y autoridades de descifrado, autentificación, verificabilidad independiente, retención de datos, controles de revoto, compatibilidad con voto familiar y actas chilenas.
2. Motor propio: especificación formal de seguridad y amenazas; credenciales anónimas/independientes, boletas cifradas, pruebas verificables, mecanismos de escrutinio, verificación individual/universal, manejo de claves, expertos y auditoría externa. No inventar criptografía ni construirlo por intuición.
Incluye diagramas de flujo de identidad/elección, matriz de amenazas y confianza, manejo de padrones/RUT, separación lógica/física, custodia de claves, recuperación, costos y riesgos. Explica cómo Google/Microsoft OAuth resuelven autenticación pero no secreto del sufragio. Precisa la política de revoto (Belenios admite modos que deben verificarse frente a los requisitos del producto). Presenta recomendación fundada y espera aprobación explícita para implementar el motor.

Prohibición: no modificar la tabla de votos para 'anonimizar' datos existentes ni marcar el producto como apto para elecciones oficiales antes del diseño y validación independiente. Hasta entonces mostrarlo como DEMO / MVP no vinculante.
7. Entregables por PR
Para cada PR: (a) ID y descripción del riesgo; (b) archivos y endpoints afectados; (c) pruebas de regresión primero y después; (d) migraciones y plan de reversión; (e) API/UI modificada; (f) riesgos residuales y pendientes; (g) evidencia de comandos ejecutados y resultados; (h) instrucciones de revisión manual.

Orden preferido:
- PR 1: secretos, URLs, demos, rate limiting, Nginx, bloqueo de resultados.
- PR 2: autorización multiinstitución, RBAC, pruebas IDOR.
- PR 3: máquina de estados, padrón congelado, horarios, resultado/tie y voto familiar concurrente.
- PR 4: migraciones, auditoría, datos personales, robustez importaciones, CI y operación.
- ADR independiente: motor criptográfico y plan de transición; no merge de módulo electoral nuevo sin autorización.
Si una PR depende de una migración estructural de otra, documenta y reajusta secuencia; prioriza conservar compatibilidad y datos. Todos los cambios de frontend necesitan protecciones equivalentes en backend.
8. Condiciones de finalización
1. Ningún secreto de voto o JWT se expone por query strings, listados, vistas previas o URLs PDF; tests automatizados lo acreditan.
2. Ningún resultado por candidatura ni acta de cierre está disponible antes del cierre; el servidor lo impide, no solo la interfaz.
3. Todos los accesos a institución/elección requieren rol y ámbito correctos; pruebas cruzadas A/B pasan.
4. Voto único por persona y por familia pasa pruebas concurrentes sobre PostgreSQL real; cierre y voto simultáneos no rompen consistencia.
5. Estados, fechas, padrón y candidaturas quedan coherentemente congelados y auditados.
6. El arranque productivo no crea cuentas ni votos de demostración, no imprime contraseñas y falla de forma segura ante secretos ausentes.
7. La configuración de despliegue y rutas reales coincide y tiene pruebas de humo; la documentación refleja exactamente la implementación.
8. La CI pasa, o cada prueba no ejecutable queda registrada como pendiente; ninguna verificación se inventa.
9. El ADR de anonimato/verificabilidad está entregado, pero el componente sigue marcado como no apto para elección vinculante hasta aprobación, implementación y auditoría.
9. Informe final que debes emitir
Entrega: resumen de vulnerabilidades encontradas y cerradas; listado de commits/PR; tabla hallazgo → corrección → prueba → resultado; migraciones; riesgos que aún bloquean producción; demo operativa verificada (si existe entorno); recomendaciones priorizadas y una lista corta de decisiones que requiere el dueño del proyecto. No confundas código compilable con plataforma electoral certificada.


Pendiente
Críticos (bloquean completitud)
#	Pendiente	Esfuerzo
P1	ADR doc/adr/001-motor-de-votacion.md — Belenios vs. motor propio, matrices de amenazas, recomendación	Alto
✅ P2	JWT → cookie HttpOnly; Secure; SameSite con CSRF (Double Submit Cookie y logout seguro)	Completado
✅ P3	Actualizar README.md — resuelto: sanitización de tokens demo, bitácora atómica, links relativos, bloqueo .xls	Completado
P4	Informe final consolidado (§9 del mandato) con recomendaciones y decisiones para el dueño	Medio


### Importantes (robustez operacional)
| # | Pendiente | Estado |
| :---: | :--- | :---: |
| ✅ P5 | Escaneo de dependencias y secretos en CI (pip-audit, gitleaks) | Completado |
| ✅ P6 | CORS configurable desde variable de entorno BACKEND_CORS_ORIGINS (fallback localhost) | Completado |
| ✅ P7 | Healthcheck /api/health con verificación activa de BD (SELECT 1 y HTTP 200/503) | Completado |
| P8 | Hashear token_votacion (sigue en texto plano) | Pendiente |
| P9 | Tests E2E con Playwright/Cypress | Pendiente |
| P10 | Validar Docker Compose y Nginx (docker compose config, nginx -t) | Pendiente |
| P11 | Verificar scripts backup.sh/restore.sh | Pendiente |
| ✅ P12 | Pinnear versiones exactas en requirements.txt (>= → ==) | Completado |
| P13 | Rate limiting persistente (Redis) para múltiples instancias | Pendiente |
| P14 | Política de retención/eliminación de PII | Pendiente |
| P15 | Bitácora append-only real (no tabla convencional) | Pendiente |
