# Sprint 2 — Cierre de brechas de seguridad, privacidad e integridad antes de Belenios

**Proyecto:** TheoGen Electoral
**Estado de este mandato:** PROPUESTO PARA EJECUCIÓN POR AGENTE IA
**Fecha de revisión:** 2026-10-27 (Chile)
**Repositorio:** https://github.com/OsvaldoVegaOses/_Electoral
**Rama base de trabajo:** fix/pr4-migrations-audit-operations
**SHA de referencia:** aa00c5d20f3db1292f899fb34cc417e10ad80ec2
**Rama principal:** main (0b654e5883145d629f331807693a1db7c9b67134 en la revisión)
**Antecedentes:** doc/sprint1.md; doc/remediacion/00-diagnostico.md y 01 a 06; doc/adr/001-motor-de-votacion.md.

> **Límite de alcance obligatorio:** este sprint mejora el sistema de gestión y el motor MVP existente solo en consistencia operacional, control de elegibilidad, privacidad y seguridad de aplicación. NO implementa Belenios ni un motor criptográfico propio; NO modifica la semántica criptográfica de las boletas, NO elimina Vote.voter_id por intuición, NO declara sufragio secreto verificable ni autoriza elecciones vinculantes. El ADR-001 permanece PROPUESTO y requiere aprobación explícita e independiente.

## 1. Encargo al agente

Actúa como ingeniero principal full-stack y de seguridad de sistemas electorales, con experiencia en FastAPI/SQLAlchemy, PostgreSQL 16, React/Vite, Playwright, migraciones Alembic, privacidad, auditoría y CI. **Examina la rama y el HEAD reales antes de editar**: los archivos y funciones aquí citados corresponden al commit de referencia, no son instrucciones para sobrescribir cambios futuros.

Objetivo: **cerrar, comprobar y documentar las brechas verificables del Sprint 1** que bloquearían el próximo estudio de integración con Belenios, preservando integridad de votos, padrones y actas. Ejecutar cinco bloques de PR pequeños e independientes, con regresiones que fallen antes y pasen después; ningún hallazgo se cierra solo con una descripción o búsqueda de texto.

### Reglas de ejecución

1. No modificar main directamente, no forzar pushes, no desplegar, no migrar BD real, no utilizar datos de escolares ni padrones reales. Abrir ramas desde la rama de desarrollo más reciente, con PR contra esa rama hasta que se prepare integración revisada a main.
2. En cada PR: constancia de SHA inicial/final, reproducción antes/después, pruebas unitarias/API y PostgreSQL real, migraciones/rollback, impacto funcional, riesgos residuales y capturas o logs **sin secretos**.
3. Si la rama avanzó, hacer rebase/merge cuidadoso sin destruir cambios. No convertir los resultados de informes anteriores en evidencia de ejecución actual. Marcar NO VERIFICADO lo que no se pudo ejecutar.
4. Cambios de esquema con Alembic y migraciones de datos separadas, probados sobre copia sintética con estados Borrador, Abierta, Cerrada y Finalizada. No usar drop/recreate en base existente ni ejecutar saneamiento silencioso.
5. Antes de operaciones irreversibles (purga, revocación masiva de credenciales, retención, cambio de historial electoral), **implementar bloqueo seguro por defecto**, documentar el procedimiento y solicitar autorización del titular del proyecto para ejecutar sobre datos operacionales.
6. Distinguir: seguridad de aplicación, integridad del proceso y secreto/verificabilidad del sufragio. Los dos primeros son el alcance del sprint; el tercero depende del ADR y auditoría externos.
7. No marcar un PR “completo” si sus pruebas críticas no están verdes y si la estrategia de despliegue/rollback no está documentada.

## 2. Línea base y matriz de hallazgos

| ID | Nivel | Hallazgo confirmado en rama de desarrollo | Archivo/área | Qué bloquea |
|---|---|---|---|---|
| S2-01 | P0 | PII: se reemplaza rut_normalizado de todos por un valor idéntico, infringiendo UNIQUE(election_id, rut_normalizado) para dos o más electores | backend/app/routers/pii.py; models.py | Anonimización |
| S2-02 | P0 | La depuración del campo familia_id altera el denominador de participación familiar, actualmente calculado desde el padrón mutable | pii.py; reports.py; models.py | Actas/estadística |
| S2-03 | P0 | Vote mantiene simultáneamente voter_id y candidate_id | models.py; voting.py | Secreto; **bloqueo de ADR, NO implementar en este sprint** |
| S2-04 | P1 | Comisión Electoral sin election_id puede operar elecciones distintas del mismo colegio | auth.py; elections.py y demás routers | Aislamiento |
| S2-05 | P1 | Se generan y conservan tokens en token_votacion en texto claro, junto al HMAC token_hash | elections.py; voters.py; voting.py; seed_data.py | Credenciales |
| S2-06 | P1 | La actualización general permite modificar calendario y metadatos de una elección abierta; config_hash no compromete todo el contenido congelado | elections.py; schemas.py | Integridad electoral |
| S2-07 | P1 | voting_entitlements.unit_key incorpora RUT/familia en claro y persiste tras depuración del padrón | models.py; elections.py; voting.py; pii.py | Privacidad residual |
| S2-08 | P1 | Cálculo de elegibilidad para retención usa fecha_creacion, y la anonimización manual no exige antigüedad mínima | pii.py; config.py | Retención indebida |
| S2-09 | P1 | Cadena de auditoría toma el último hash sin serialización transversal de escritores; eliminación de prefijos y anclaje local requieren prueba rigurosa | auth.py; audit.py; pii.py; migración e5f6a7b8c9d0 | Integridad probatoria |
| S2-10 | P1 | El anclaje externo es una recomendación de exportación, no evidencia de que exista custodia independiente | audit.py; doc/remediacion/06-* | Verificabilidad de la bitácora |
| S2-11 | P1 | CI está definida, pero no se confirmó un run exitoso del HEAD; Playwright no está incorporado como gate y Gitleaks tolera fallos | .github/workflows/ci.yml; frontend/e2e | Calidad/release |
| S2-12 | P1 | Contrato de rate limiting Redis/fallback y controles de cookie/cabecera requieren adversarial y configuración fail-closed de producción | auth.py; main.py; rate_limiter.py; config.py | Autenticación/antiabuso |
| S2-13 | P2 | Informes previos no coinciden por completo con las modificaciones y existe duplicación del ADR en doc/motor | doc/*; README.md | Gobierno documental |

**Restricción:** S2-03 se registra como riesgo crítico residual. No debe declararse resuelto por ninguna PR del Sprint 2.

## 3. Secuencia de ejecución y entregas

### PR S2-A — Contención segura, permisos estrictos y pruebas de regresión

**Objetivo:** cerrar acceso horizontal por comisión y evitar ejecuciones inseguras de tratamientos PII mientras se prepara la migración completa.

**Archivos:** backend/app/auth.py; backend/app/routers/elections.py; backend/app/routers/pii.py; backend/tests/test_s2_a_permissions_and_guards.py; migración si resulta imprescindible.

Tareas:
1. En check_election_access, cuando rol sea Comisión Electoral, exigir **ambos** school_id y election_id, y que corresponda a la elección consultada. Si election_id es NULL, denegar por defecto (403) salvo flujo explícito y auditado de asignación. Verificar el mismo control en list_elections, estadísticas, candidatos, padrón, auditoría y actas. No inferir permiso de toda la institución por no tener asignación.
2. Validar las asignaciones school_id/election_id al crear o modificar usuarios. Rechazar asociaciones contradictorias y usuarios institucionales sin institución. Migración y procedimiento de reparación de registros legacy sin elevar privilegios accidentalmente.
3. Si el endpoint de anonimización/purga todavía puede dañar registros o evidencia, **inhabilitar su ejecución por defecto en producción** con respuesta y documentación claras hasta completar PR S2-C; conservar lectura/status y dry-run. No ejecutar tratamientos destructivos como parte de pruebas sobre información real.
4. Agregar pruebas negativas con dos colegios, dos elecciones de un mismo colegio, comisiones con y sin election_id, responsable institucional y superadmin; HTTP reales contra el backend, con 403 para acciones no autorizadas. Revisión por API directa, no confiar en componentes React.

**Aceptación:** cero lecturas/escrituras fuera de ámbito; cero promoción implícita; PII/purga no pueden ejecutarse inadvertidamente con defectos conocidos; tests de Sprint 1 intactos.

### PR S2-B — Congelamiento electoral, instantánea íntegra y denominadores estables

**Objetivo:** definir fuente de verdad de configuración y de unidades electorales, que sobrevivirá a depuración de datos personales.

**Archivos:** backend/app/models.py; schemas.py; routers/elections.py, voters.py, candidates.py, reports.py y voting.py donde corresponda; migraciones Alembic; tests/test_s2_b_election_snapshot.py; frontend si se requiere bloquear acciones.

Tareas:
1. Después de apertura, impedir cambios en fecha_inicio, fecha_fin programada, nombre/papeleta si aparece en actas, reglas, tipo, colegio, lista de candidatos, comisiones y padrón. Si se necesita reprogramación/suspensión excepcional, **no crear atajos por PUT**: entregar primero propuesta de transición y acta/autoridad competente. Distinguir hora de cierre efectivo de hora programada; no sobrescribir silenciosamente el cronograma original.
2. Construir una **instantánea versionada determinista** con JSON canónico (orden estable, fechas ISO UTC y versión de esquema) de las reglas, candidaturas, calendario, cantidades y compromisos privados del padrón. No introducir RUT ni hash simple enumerable de RUT en un archivo o hash público. Versionar el contenido sensible bajo custodia privada y publicar solo evidencia no identificante. Un hash dependiente de datetime.now(), sin instantánea reproducible, **no satisface** este requisito.
3. Calcular/guardar, bajo transacción de apertura y con checks, número de personas del padrón, número de unidades habilitadas, lista o recuento de derechos familiares y configuración válida. El denominador del escrutinio/acta debe provenir de esta instantánea o entitlements congelados; no recalcularse desde Voter.familia_id después de la depuración.
4. Para elecciones ya abiertas/terminadas, diseñar migración backfill **solo si existe evidencia suficiente** para reconstruir números; de lo contrario registrar “requiere conciliación” y bloquear acta definitiva nueva en vez de inventar datos.
5. Verificar integridad de la instantánea al cerrar y al generar acta. Si se detecta divergencia, emitir error/auditoría y requerir revisión humana.

**Pruebas de aceptación:** misma configuración = misma huella; cambio de un dato electoral altera huella; RUT no filtrado en evidencia pública; un padrón familiar de 5 personas/2 unidades registra 2 habilitadas y conserva porcentaje tras depuración; rechazos 409/403 de cambios extemporáneos; pruebas PostgreSQL de apertura/cierre concurrentes. No alterar votos históricos.

### PR S2-C — Privacidad, retención y ciclo de vida seguro de credenciales

**Objetivo:** cerrar fallas reproducibles de PII y eliminar persistencia innecesaria de secretos sin bloquear a electores legítimos.

**Archivos:** backend/app/models.py; app/routers/pii.py, voters.py, elections.py y voting.py; app/auth.py y config.py; doc/remediacion/05-politica-retencion-pii.md; nueva(s) migración(es); tests/test_s2_c_pii_and_tokens.py.

Tareas PII y retención:
1. Corregir el conflicto de unicidad: para registros depurados, rut_normalizado debe quedar NULL u otro diseño realmente sin identificador, compatible con restricciones; el valor genérico de rut (NOT NULL) puede mantenerse como etiqueta si no introduce colisiones. No eliminar índices únicos que protegen el padrón activo. Test de 2, 10, 100 electores y dos colegios, más repetición/idempotencia.
2. Eliminar también identificadores residuales en voting_entitlements.unit_key: hoy expone valores RUT:<rut> y FAM:<familia_id>. Proponer esquema de identificador opaco aleatorio por unidad **sin romper unicidad ni historial**, con manejo de migración para entitlements previos. No dar por anónimo un identificador derivado de RUT. Tratar backups, logs y reportes como fuentes de reidentificación.
3. Depurar los campos familiares únicamente **después** de que la instantánea/denominador y expediente hayan sido congelados (PR S2-B); probar que las actas conservan los totales antes y después. Mantener RUT y correlaciones bajo controles privados mientras legalmente sean imprescindibles; no convertir la purga en eliminación prematura de pruebas de impugnación.
4. Corregir la elegibilidad de retención: no contar desde Election.fecha_creacion. Definir fecha de cierre/finalización inequívoca e inmutable, con migración. Asegurar que el endpoint manual también aplique plazo y legal hold, no solo la vista “ready”. No aplicar por defecto 90/365 días como si fueran plazos legalmente obligatorios; obtener aprobación jurídica por tipo de organización y documentar parámetros.
5. Revisar cadena de purga: eliminación de logs antiguos rompe o recorta evidencia; impedir purga no autorizada, preservar anclas/épocas de cadena y demostrar verificación post-retención. Los respaldos que contienen PII deben tener plazos, control de cifrado y proceso de expurgo coordinados.
6. Reconocer explícitamente que Vote.voter_id + candidate_id sigue vinculando selección e identidad: **el tratamiento será minimización o seudonimización parcial, no garantía de anonimato del sufragio**. No modificar esa tabla para simular secreto.

Tareas credenciales:
7. Dejar de guardar nuevas credenciales sin cifrar en token_votacion **una vez diseñado y probado un canal real de entrega de un solo uso**. La BD debe conservar solo material derivado de verificación; los hashes/HMAC no se envían al elector ni se vuelven tokens válidos. Cuidado con referencias antiguas: el comportamiento de compatibilidad debe ser transitorio, inventariado y deshabilitado en producción tras migración.
8. Para altas/importaciones/reeemisiones, establecer operación transaccional de provisión + entrega segura o estado de envío pendiente; si no existe mensajería real, fallar de forma segura en producción y mostrar “entrega no implementada”. Nunca imprimir tokens por API administrativa, CSV, preview, URL o logs.
9. Diseñar rotación/reemisión que invalide la credencial anterior, con prueba de autorización, recuperación de fallos de envío y protección contra duplicados. No invalidar silenciosamente credenciales de una elección en curso; ante datos reales, preparar plan de migración y pedir autorización.
10. Ejecutar escaneo de exposición de secretos en frontend/backend y respuestas; revisar correo simulado, autenticación, encabezados, enlaces, PDFs y registros.

**Pruebas:** 2+/100 electores finalizados sin IntegrityError; 100% de índices de padrón activo intactos; denominador invariable; endpoint manual rechaza vencimiento prematuro/legal hold; segundo intento idempotente; unidad opaca sin RUT en DB/listados de acceso no autorizados; tokens nuevos ausentes de almacenamiento en claro, logs, URLs y APIs; credencial revocada rechazada; ruta legacy detectada y planificada sin revocar votos.

### PR S2-D — Cadena de auditoría concurrente y anclaje verificable

**Objetivo:** que el registro de eventos simultáneos, su verificación y conservación no dependan de supuestos falsos de inmutabilidad.

**Archivos:** backend/app/auth.py; routers/audit.py, pii.py; models.py; migración e5f6a7b8c9d0 o siguiente; doc/remediacion/06-arquitectura-bitacora-append-only.md; tests/test_s2_d_audit_concurrency.py.

Tareas:
1. El algoritmo de log_audit lee el último record_hash y luego hace INSERT sin reservar el “head”. Diseñar serialización **a nivel PostgreSQL** de escritores de la cadena (por ejemplo fila cabeza bloqueada transaccionalmente o advisory lock bien definido), incluyendo múltiples workers y transacciones de negocio; no depender de un Lock Python por proceso. Mantener atomicidad del evento y su negocio o documentar un outbox real.
2. Definir serialización canónica y orden total (por ID/secuencia), manejo de rollback, pérdidas, reintentos y eventos legacy sin hash. Asegurar que eventos exitosos simultáneos no generan dos hijos del mismo prev_hash. Probar con 50–100 escrituras simultáneas y verificar todas.
3. Trigger PostgreSQL append-only debe impedir edición por roles normales, pero reconocer que un administrador privilegiado puede alterar reglas o desactivar triggers. No llamar “inmutable” sin controles externos.
4. Resolver la tensión entre retención/purga y verificación: definir épocas/puntos de corte y cadena verificable que no trate el primer evento retenido como una nueva génesis falsa; prueba de borrado inicial, medio y final y ancla externa previa.
5. Completar anclaje independiente: al menos artefacto exportable con head_hash, última secuencia, número de eventos, sello temporal y digest verificable; **una respuesta JSON del mismo servidor no basta**. Si no es posible operar WORM/TSA/sistema ajeno en pruebas, marcar “pendiente de evidencia externa”, no “cumplido”.
6. Proteger identidades/datos personales en logs antes de fijar anclas; documentar limitaciones de corrección posterior de contenido comprometido.

**Pruebas:** 50–100 eventos de múltiples sesiones PostgreSQL sin ramas de hash; rollback sin evento huérfano; detección de modificación/supresión/truncamiento contra checkpoint externo; validación sobre backup restaurado; rol no privilegiado no altera ni borra; purga conservadora compatible con verificación.

### PR S2-E — Integración, pruebas end-to-end, CI y cierre documental

**Objetivo:** convertir correcciones dispersas en una versión candidata reproducible, revisable y con evidencias.

**Archivos:** .github/workflows/ci.yml; backend/tests/*; frontend/e2e/* y playwright.config.js; frontend/package.json/package-lock.json; README.md; doc/remediacion/07-informe-sprint2-cierre.md; doc/sprint1.md solo para referencias/estado histórico, sin reescribir evidencia anterior.

Tareas:
1. Ejecutar CI completo sobre SHA final de la rama: tests backend con PostgreSQL 16, migración Alembic upgrade/downgrade/upgrade sobre base vacía y simulación de actualización en base no vacía, sintéticos con datos activos y finalizados, lint/build frontend.
2. Incorporar Playwright como paso requerido de CI; levantar stack de prueba, instalar navegadores/dependencias, ejecutar login/logout/CSRF, creación/apertura, voto familiar, cierre, acta y rechazos por rol. Usar fixtures ficticios, no datos de niños.
3. Hacer bloqueantes los escaneos reales de secretos y dependencias: retirar continue-on-error de Gitleaks cuando la herramienta/licencia estén operativas; explicar y resolver falsos positivos de forma controlada, nunca con desactivación global. Verificar npm ci / bloqueo de dependencias, versiones Node y Python compatibles.
4. Verificar, con ejecución real, docker compose config, nginx -t, aislamiento de PostgreSQL, TLS/proxy/cabeceras, backup + restore en ambiente sintético, y healthchecks. Demostrar recuperación sin perder votos reconocidos; no limitarse a búsquedas de texto.
5. Añadir pruebas adversariales para Redis (contadores concurrentes, expiración, dos workers, unavailable/degraded), cookies HttpOnly/Secure/SameSite, CSRF al enviar cabecera Authorization con cookie presente, y prioridad coherente entre credenciales cookie/header. **En producción multiinstancia, ausencia de Redis no debe degradar silenciosamente controles de abuso**: decidir política fail-closed o mecanismo alternativo robusto y demostrarlo.
6. Verificar contract tests para PII, auditoría, RUT/duplicados, familia, zonas horarias y descarga PDF. Retirar mensajes que afirmen “oficial”, “voto secreto”, “sellado irreversible/verificable” mientras no exista urna auditada.
7. Actualizar manual de puesta en marcha, registro de riesgos residual y duplicaciones documentales. Conservar ADR-001 como PROPUESTO; no marcarlo aprobado ni integrar Belenios.
8. Preparar PR final de integración **sin fusionar automáticamente** a main. Solicitar revisión de seguridad, de producto y, cuando corresponda, jurídica.

**Aceptación:** CI verde vinculada a SHA, enlace a ejecuciones, tests E2E efectuados con evidencias, pruebas de PostgreSQL real y migraciones; si un servicio no está disponible, resultado marcado PENDIENTE y release bloqueada, no aprobado ficticio.

## 4. Casos de prueba obligatorios de punta a punta

| Caso | Preparación | Resultado obligatorio |
|---|---|---|
| PII-100 | 100 electores de una elección Finalizada | Anonimización sin colisión UNIQUE ni pérdida de totales |
| PII-FAM | 5 personas pertenecientes a 2 familias; 1 voto | Denominador=2 y participación=50% antes/después de PII |
| PII-LEGAL | Elección finalizada reciente o con legal hold | Anonimización manual/automática bloqueada |
| PII-ID | Padrón purgado, consultas a tablas/backup accesible | No quedan RUT/familia innecesarios fuera de custodia; riesgos residuales documentados |
| RBAC-NULL | Comisión sin election_id; dos elecciones del mismo colegio | 403 en detalles, mutaciones, actas, padrón y resultados |
| RBAC-CROSS | Responsable colegio A intenta leer B | 403, sin respuestas parciales |
| SNAP | Alterar un dato de configuración antes/después apertura | Hash reproducible; tras apertura 409 o flujo formal autorizado |
| TOK-NEW | Nueva credencial y envío seguro simulado | Texto claro no persistido ni retornado en endpoints administrativos |
| TOK-OLD | Credencial vieja en elección abierta | No invalidación silenciosa; plan y autorización de migración |
| AUD-100 | 100 escrituras paralelas en sesiones PostgreSQL distintas | Cadena lineal válida sin forks ni registros perdidos |
| AUD-PURGE | Purga reglada de prefijo y archivo independiente | Verificación sigue válida con anclas/épocas; si no, purga prohibida |
| REDIS-OFF | Redis caído en ambiente multiworker | Protección antiabuso no se degrada silenciosamente |
| CSRF | Cookie auth sin header CSRF y con header Bearer inyectado | Política definida, testada, sin salto de controles |
| E2E-FULL | Dos colegios, comisión, votantes, candidatos, PDF | Flujo funcional correcto y aislamiento cross-tenant |
| CRYPTO | Intentar reconstruir selección desde Vote.voter_id/candidate_id | Riesgo identificado como P0 residual; **no exigir secreto probado hasta integración autorizada** |

## 5. Gobierno y definición de terminado (DoD)

El Sprint 2 solo se declarará “cerrado para iniciar estudio/PoC de Belenios” cuando:

1. PII masiva, denominador familiar y retención demuestren integridad con varias filas y sin reidentificación accidental por identificadores residuales.
2. Comisión sin asignación explícita no acceda a ninguna elección; roles y ámbitos correctos en toda la API.
3. Configuración electoral/denominadores tengan instantánea estable y los endpoints respeten congelamiento y horarios.
4. El almacenamiento de secretos y entrega de credenciales sea consistente, con migraciones seguras y sin exposición en producción.
5. La auditoría sea lineal bajo concurrencia real; checkpoint externo documentado/ensayado o riesgo y operación bloqueante declarados.
6. Las pruebas reales de concurrencia PostgreSQL 16, migraciones, build, Playwright, escáneres y backup/restauración pasen en el SHA final. Si una está ausente, **NO-GO**.
7. Se emita informe de cierre con tabla ID→evidencia antes→código→prueba→resultado→riesgo residual; enlaces a commits, PR, jobs y logs.
8. Una persona revisora independiente del agente confirme que no se introdujeron regresiones de privacidad, autorizaciones o datos electorales.
9. El ADR-001 permanezca en estado PROPUESTO hasta decisión escrita. **Cerrar Sprint 2 NO equivale a autorizar elecciones vinculantes o comenzar el motor.**

### Criterio explícito de release

- **NO-GO** ante cualquier P0/P1 sin test y mitigación; ante divergencia de escrutinio; falta de seguridad/retención de PII; pérdida de cadena de auditoría; no disponibilidad del informe de ejecución.
- **GO limitado**: habilita únicamente proponer al titular una prueba aislada de interoperabilidad con Belenios, **cuando autorice por escrito el Gate G1 del ADR-001**, con datos ficticios y sin despliegue oficial.
- El secreto/verificabilidad del voto sigue bloqueado por Vote.voter_id y candidate_id; no se considera éxito de Sprint 2.

## 6. Informe obligatorio del agente

Crear **doc/remediacion/07-informe-sprint2-cierre.md** con:

1. Estado inicial (HEAD, ramas, fecha, pruebas base, cambios ajenos).
2. Matriz de riesgos S2-01…S2-13 con estado REAL: VERIFICADO-CERRADO, MITIGADO, PENDIENTE, NO APLICA (fundamentar).
3. Resumen por PR con diffs, migraciones y pasos de rollback.
4. Tabla de pruebas: comando, entorno/versión, cantidad, resultados, enlace a logs CI y límites; incluir pruebas fallidas/pendientes.
5. Informe de integridad del padrón, participación familiar, PII y expedientes antes/después de migraciones sintéticas.
6. Informe de auditoría concurrente, anclas externas y cualquier riesgo de actor con privilegios DBA.
7. Evidencias de CORS, CSRF, cookies, autenticación y Redis ante fallas.
8. Advertencia vigente sobre secreto/verificabilidad electoral y prohibición de uso vinculante.
9. Propuesta concreta de avance al Gate G1 del ADR-001 **sin ejecutar la PoC**.
10. Decisiones que debe aprobar el titular del proyecto: retención y legal holds, canal de entrega de credenciales, tratamiento de elecciones legadas, política de anclaje y autorización de integración.

## 7. Primer mensaje de ejecución sugerido al agente

> Lee doc/sprint2.md completo en la rama de desarrollo. Verifica HEAD y diagnostica los hallazgos contra el código. Comienza exclusivamente por PR S2-A con tests de regresión reproducibles antes del cambio. No ejecutes PR posteriores hasta entregar evidencias y confirmar que PR S2-A pasa. No modifiques el motor criptográfico ni uses datos electorales reales. Al concluir el sprint entrega doc/remediacion/07-informe-sprint2-cierre.md y una decisión GO/NO-GO fundada; no fusiones main ni implementes Belenios sin aprobación explícita.

---
**Estado:** documento de instrucciones. **No es evidencia de pruebas ejecutadas ni aprobación de implementación del motor.**
