# Plan de cierre de pendientes del Sprint 2

Fecha: 2026-10-28, Chile. Estado: plan preparado; implementación y validaciones pendientes. El Sprint 2 continúa NO-GO.

## 1. Determinación y alcance

Se puede completar ahora una parte importante del trabajo de código, pruebas y documentación. PostgreSQL 16, Redis 7, concurrencia, migraciones, Playwright y backup/restauración necesitan servicios reales de prueba, pero pueden ejecutarse en Docker local: no requieren contratar servidores ni desplegar producción.

El cierre completo también depende de evidencia CI del SHA final, custodia independiente, entrega real de credenciales y decisiones humanas. Disponer de Docker no demuestra que esas condiciones estén cumplidas.

Se conserva la decisión documentada de diferir el paquete HMAC de `unit_key` y no modificar el motor en este cierre. Esta decisión resuelve el alcance, pero **no cierra S2-07**. Para cumplir íntegramente el mandato original habrá que autorizar por separado su corrección o aprobar una modificación expresa del alcance y sus restricciones. Una exclusión del commit no transforma un hallazgo P1 en resuelto.

S2-03 (`Vote.voter_id` junto a `candidate_id`) permanece como riesgo crítico residual expresamente fuera del Sprint 2. Este plan no propone quitar columnas ni implementar Belenios. El cierre del sprint tampoco autoriza elecciones vinculantes ni sustituye el Gate G1 del ADR-001.

## 2. Base comprobada y límites de la evidencia

| Elemento | Evidencia disponible | Límite |
|---|---|---|
| Rama y HEAD | `fix/s2-c-pii-privacy-tokens`, `65c164c7bb4073d5250c04d8f8cb40095a759ffb` | S2-A y S2-B tienen commits; los cambios posteriores siguen en el árbol de trabajo. No existe aún un candidato final seleccionado. |
| Backend | En el turno anterior de esta revisión: `pytest tests -q -rs`, **136 passed, 8 skipped**, con configuración local SQLite | No se ejecutaron PostgreSQL ni Redis reales. No es certificación del futuro candidato sin HMAC. |
| Lint | Ejecutado en el turno anterior: salida 0, con advertencias | No acredita build, E2E ni seguridad operacional. |
| Playwright | Último `.last-run.json` conservado: `failed`; contexto: rechazo del login | No se repitió Playwright al preparar este plan. El registro previo de 7 aprobados no sustituye una ejecución sobre el candidato final. |
| Docker | Consulta actual: servidor **29.1.2**; imágenes `postgres:16`, `postgres:16-alpine` y `redis:7-alpine` presentes | Se comprobó disponibilidad, no se levantó el laboratorio Sprint 2. Solo se observaron cuatro contenedores activos del PoC Belenios. |
| Nginx | No apareció una imagen `nginx:*` en el inventario consultado | Hará falta obtener una imagen de prueba o construir la imagen frontend. Acceso y compatibilidad se comprobarán al ejecutar. |
| Infraestructura externa | El informe de cierre mantiene pendientes CI, custodia y canal de entrega | No se consultaron cuentas externas ni se certificó disponibilidad, permisos, costes o configuración de esos servicios. |

La nota del informe que atribuye el bloqueo a Docker no disponible está desactualizada. La falta actual es de preparación y ejecución del laboratorio, además de los bloqueos externos y de alcance.

Fuentes locales: [mandato y DoD](../sprint2.md), [informe de cierre](../remediacion/07-informe-sprint2-cierre.md), [workflow](../../.github/workflows/ci.yml), [política PII](../remediacion/05-politica-retencion-pii.md) y [arquitectura de auditoría](../remediacion/06-arquitectura-bitacora-append-only.md). Ante diferencias documentales, registrar la decisión vigente y conservar la evidencia histórica.

## 3. Qué puede cerrarse ahora y qué necesita infraestructura

“Puede cerrarse ahora” significa que el trabajo y sus pruebas pueden realizarse con los recursos locales disponibles, no que ya esté terminado. La aceptación formal exige la evidencia indicada.

| Pendiente | Qué se puede resolver ahora | Requisito adicional para aceptarlo | Clasificación |
|---|---|---|---|
| Selección de cambios sin HMAC | Preparar candidato aislado, separar hunks y conservar el trabajo diferido | Revisar compatibilidad del candidato y su historial Alembic | Código local |
| Puertos PostgreSQL y omisiones silenciosas | Sustituir `5439` fijo por configuración de prueba; fallar si falta un servicio obligatorio en CI | Ejecutar las pruebas con PostgreSQL 16 real | Código local + Docker |
| Cadena de migraciones | Separar la dependencia auditoría → HMAC; revisar modificaciones a migraciones ya versionadas | Upgrade/rollback/upgrade y datos sintéticos en PostgreSQL 16 | Código local + Docker |
| RBAC, congelamiento, denominadores y PII | Completar pruebas y corregir regresiones del candidato | Contratos locales y PostgreSQL; revisión del riesgo residual S2-07 | Código local + Docker |
| Concurrencia de auditoría y votos | Completar escenarios con sesiones y procesos independientes | PostgreSQL 16; roles de aplicación sin privilegios de propietario | Docker local |
| Redis y protección ante fallos | Completar pruebas multiworker, concurrencia, expiración y caída | Redis 7 real y dos procesos de aplicación de prueba | Docker local |
| E2E completo | Fixtures deterministas, login, CSRF, voto familiar, cierre, acta y roles | PostgreSQL, backend, frontend y navegador de prueba | Laboratorio local; repetición en CI |
| Compose, Nginx, TLS y restauración | Preparar red aislada, certificados de prueba y recuperación de datos sintéticos | Imágenes/herramientas y ejecución local; para dominio/certificado desplegado, entorno externo específico | Docker local; validación desplegada separada |
| CI y artefactos | Reparar workflow, publicar reportes y hacer obligatorios los controles | Acceso al repositorio, runner y un run exitoso del SHA final; permisos para controles requeridos si procede | Servicio externo de CI |
| Checkpoint de auditoría | Exportación, digest y verificación contra cadena restaurada o alterada | Custodio fuera del control de la aplicación, recibo y verificación independiente | Infraestructura/custodia externa |
| Credenciales | Diseño, implementación y pruebas de provisión, envío, fallos, reemisión y revocación con un receptor local | Canal real autorizado, identidad emisora y secretos persistentes; prueba con destinatarios sintéticos controlados | Código local + servicio de entrega |
| Retención, legal hold y datos legacy | Propuesta de política, inventario sintético, procedimiento y ensayo de recuperación | Decisión del responsable del proyecto y revisión jurídica; autorización específica antes de datos operacionales | Decisión humana, no compra de infraestructura |
| Privacidad residual de `unit_key` | Inventariar exposición, controles de acceso y restricciones; separar el paquete diferido | Decisión de alcance; si se autoriza corregir, implementación coordinada y migración/recuperación probadas | Alcance + código; secretos persistentes si se adopta HMAC |
| Informe final y revisión | Completar matriz S2-01…13, trazabilidad y manual | Evidencias finales, revisión independiente y aceptación escrita | Documentación + revisión humana |

## 4. Secuencia de ejecución y criterios de salida

### Etapa 0 — Preparar un candidato coherente y conservar el trabajo existente

Responsable: ingeniería. Dependencia: ninguna para preparar el candidato dentro del alcance vigente.

1. Registrar HEAD, inventario y diferencias; preparar un checkout/candidato aislado desde la base comprobada. No borrar, sobrescribir ni mezclar los cambios diferidos del árbol original.
2. Excluir documentos del PoC, resultados generados de Playwright y el paquete HMAC completo: lector en `voting.py`, derivación al abrir elecciones, helper, configuración, migración, comentarios y pruebas exclusivos. Separar por hunk los archivos mixtos, conservando los controles independientes de credenciales, PII y auditoría.
3. **Resolver la dependencia Alembic:** `c3d4e5f6a7b8` tiene `down_revision = b2c3d4e5f6a7`, precisamente la migración HMAC excluida. En el candidato, preparar una ruta válida de auditoría sin arrastrar HMAC. No basta con omitir el archivo `b2...`. Verificar un único head y toda la cadena. No reescribir revisiones ya publicadas o aplicadas: si se detecta ese caso, preparar una estrategia de compatibilidad antes de continuar.
4. Revisar los cambios actuales a `f6a7b8c9d0e1`, que ya pertenece al HEAD versionado. Resolver qué corresponde a una revisión posterior y probar tanto actualización desde S2-B como instalación desde cero; no suponer que editar una migración vuelve a ejecutarla en bases que ya la aplicaron.
5. Separar el assert de backfill HMAC en `test_s2_migration_postgres.py` y su fixture, manteniendo la prueba de denominadores. Revisar `test_s2_c_pii_and_tokens.py` sin descartar sus pruebas independientes de privacidad y retención.
6. Registrar S2-07 como pendiente y describir límites de acceso, exportación y tratamiento PII mientras sobrevivan identificadores residuales. Conservar las operaciones destructivas bloqueadas en producción.

Criterio de salida: candidato revisable sin imports/configuración/migraciones HMAC huérfanos, ruta Alembic consistente y manifiesto de cambios incluidos/excluidos. Las pruebas anteriores del árbol completo no se heredan como aprobación del candidato.

### Etapa 1 — Corregir la preparación de pruebas y CI

Responsable: ingeniería. Dependencia: etapa 0.

1. Parametrizar las conexiones de `test_pr3_state_machine_concurrency.py` y `test_pr4_migrations_audit_operations.py`. Ambos usan PostgreSQL `5439`; el workflow publica `5432`. Usar URLs de integración explícitas y bases desechables separadas, sin introducir credenciales en logs.
2. En los controles obligatorios de CI, convertir servicio ausente/inaccesible en fallo. Revisar los skips de módulos PostgreSQL y del fixture Redis; mantener claramente diferenciadas las suites unitarias que sí pueden omitir integración al ejecutarse sin servicios.
3. Aislar las pruebas que hacen `drop_all/create_all` o downgrade. No deben borrar el esquema donde otro grupo comprueba migraciones o la cadena de auditoría. La preparación de datos y el DDL automático de desarrollo no deben ocultar una migración ausente.
4. Corregir o retirar de la recolección automática `backend/test_setup.py`: crea datos sobre la base configurada e imprime PII y un token. La suite canónica debe ser explícita y cualquier comprobación de setup debe usar datos efímeros y salida sin secretos.
5. Preparar fixtures de E2E propios por ejecución: administrador, dos colegios, comisiones con/sin asignación, candidatos y familias. Usar el intérprete del entorno correcto y puertos exclusivos; no reutilizar un backend arbitrario ni una SQLite previa. No depender de contraseñas demo existentes.
6. Configurar JUnit/HTML de Playwright, reporte de backend y carga de artefactos CI incluso ante fallo, con revisión de trazas, capturas y URLs para evitar exponer credenciales. El workflow actual no contiene pasos `upload-artifact` y Playwright solo configura reporter de lista.
7. Revisar el control `nginx -t`: `frontend/nginx.conf` usa upstream `backend:8000`. La invocación de un Nginx aislado debe disponer de esa resolución en una red sintética; comprobarlo al ejecutar, sin dar por validada la configuración por su sola presencia.

Criterio de salida: comandos y workflow preparados, fixtures repetibles, ninguna prueba obligatoria puede aprobarse por skip y los grupos destructivos usan bases exclusivas.

### Etapa 2 — Ejecutar el laboratorio local completo

Responsable: ingeniería. Dependencias: etapas 0 y 1.

Preparar un Compose de pruebas con nombre de proyecto, volúmenes, red y contenedores propios, sin los `container_name` globales de desarrollo. Publicar puertos solo en loopback y comprobar disponibilidad antes de asignarlos. No tocar los cuatro contenedores Belenios existentes ni reutilizar `theogen_electoral.db`. Comprobar espacio/RAM, herramientas e imágenes antes de ejecutar; obtener las que falten. Los datos serán exclusivamente sintéticos.

| Grupo | Ejecución necesaria | Evidencia para aceptar |
|---|---|---|
| Migraciones | Base vacía: upgrade → downgrade → upgrade. Base poblada: Borrador, Abierta, Cerrada y Finalizada; denominadores reconstruibles/no reconstruibles; actualización desde S2-B ya aplicado | Revisión inicial/final, datos antes/después, invariantes y rollback real. Si una transformación de datos no admite downgrade, demostrar restore protegido; no llamar reversible a lo que no lo es. |
| RBAC y configuración | Dos colegios, dos elecciones por colegio, comisión sin asignación y asignaciones contradictorias; congelamiento/horarios/snapshot | 403/409 correspondientes, ninguna filtración parcial y misma configuración con misma huella. |
| PII y participación | 2/10/100 electores, dos colegios, idempotencia, elección reciente, sin cierre verificable y con legal hold | Sin colisiones; índices del padrón activo intactos; 5 personas/2 familias/1 voto conservan denominador 2 y participación 50%. Inventariar `unit_key` residual sin declarar anonimato completo. |
| Votos y auditoría | Doble voto por persona/familia, carrera voto/cierre; 100 escrituras de auditoría, rollback y dos procesos independientes | Un único voto válido, sin deadlocks, cadena lineal y head correcto. Rol normal no modifica/borra logs; alteración/truncamiento detectados. |
| Redis y autenticación | Dos procesos/clientes, contadores simultáneos, expiración, caída al inicio y durante uso; cookies y mezcla cookie/Bearer/CSRF | Contadores compartidos y bloqueo seguro en configuración productiva; sin degradación silenciosa a memoria. Cookies y rechazos CSRF verificados por HTTP/navegador. |
| E2E completo | Crear/configurar elección, padrón, apertura, voto familiar y rechazo de segundo miembro, cierre, acta/PDF, roles, login/logout | Reporte y trazas sanitizadas del flujo completo; no limitarse a mostrar candidatos. |
| Operación | Compose, Nginx en red válida, HTTPS con certificado de prueba, proxy/cabeceras, health y puertos de BD no públicos | Resultados reales. TLS local demuestra configuración del laboratorio, no dominio/certificado de un despliegue externo. |
| Recuperación | Backup de votos sintéticos reconocidos, checksum, restauración en una base desechable y verificación posterior | Mismos votos reconocidos, denominadores y cadena/checkpoint. Comparar identificadores/hashes y contenido, además de recuentos. |
| Calidad y exposición | Instalación desde lockfile, lint/build, escaneo de dependencias/secretos y respuestas/HTML/PDF/logs | Resultados sobre el candidato, hallazgos corregidos o excepciones específicas revisadas. No desactivar globalmente escáneres. |

Criterio de salida: todos los controles locales obligatorios ejecutados y aprobados; fallos y skips explicados sin equivaler a aceptación. Repetir los grupos afectados después de cada corrección. Limpiar únicamente recursos creados por el laboratorio tras verificar su identidad y conservar evidencia sanitizada.

### Etapa 3 — Completar credenciales y privacidad dentro del alcance autorizado

Responsables: ingeniería y titular del proyecto. Preparación independiente; integración después de etapas 0–2 y de las decisiones aplicables.

1. Diseñar el ciclo de provisión y entrega: estados, reintentos, duplicados, fallo parcial, reemisión autorizada y momento de invalidación de la credencial previa. Evitar persistencia en claro y exposición por API, CSV, preview, URL, PDF o logs. Probar primero con receptor local controlado; eso valida el contrato, no una entrega externa.
2. Mantener el bloqueo productivo hasta que exista implementación y prueba del canal real. `require_credential_delivery()` actualmente bloquea incondicionalmente en producción: disponer de un servidor de correo por sí solo no implementa el canal.
3. Conservar el paquete HMAC diferido. Si se autoriza posteriormente S2-07, revisar el diseño de identificadores opacos y desplegar coordinadamente lector, provisión, migración y recuperación de claves. Con HMAC, exigir secreto persistente independiente, copia protegida y recuperación que reproduzca los mismos identificadores. HMAC es seudonimización, no anonimato del sufragio.
4. Si no se autoriza corregir S2-07, conservarlo abierto. Para aceptar un alcance reducido se necesita una decisión escrita que cambie el alcance/DoD y sus restricciones; no declarar cerrado el Sprint 2 original solo porque pasen los tests del subconjunto.

Criterio de salida: contrato e implementación local de entrega probados; canal productivo y privacidad residual conservan su estado pendiente hasta las evidencias y decisiones correspondientes. Ninguna credencial de una elección real se revoca por este plan.

### Etapa 4 — Obtener evidencia externa y decisiones humanas

Estas dependencias pueden prepararse mientras avanza el laboratorio. No requieren contratar necesariamente servicios nuevos: primero confirmar qué recursos y custodios existentes son aptos.

| Dependencia | Responsable | Insumo mínimo | Criterio de aceptación |
|---|---|---|---|
| CI del candidato | Ingeniería / administración del repositorio | Acceso al repositorio y runner; escáneres utilizables | SHA publicado idéntico al revisado; todos los jobs requeridos aprobados; sin skips obligatorios; URLs, logs y artefactos conservados. Publicar según las autorizaciones vigentes, sin fusionar automáticamente. |
| Custodia del checkpoint | Responsable de auditoría / custodio independiente | Destino y permisos fuera del control de la aplicación; política de conservación | Artefacto con head, secuencia, conteo, fecha y digest; recibo identificable; un tercero recupera y verifica. Alteración/truncamiento de una copia debe detectarse frente al artefacto custodiado. |
| Entrega real de credenciales | Producto / operación / ingeniería | Canal aprobado, identidad emisora y secretos persistentes | Entrega a destinatarios sintéticos controlados, prueba de fallo/reintento/duplicado/reemisión/revocación y ausencia de exposición. No contactar electores reales como prueba. |
| Retención y legal hold | Titular / asesoría jurídica | Propuesta por tipo de dato, organización, backups y expediente | Plazos, inicio del cómputo y responsables para activar/liberar holds aprobados por escrito. Los defaults técnicos no son aprobación jurídica. |
| Auditoría legacy | Titular / responsable de datos | Inventario sin PII expuesta; backup y propuesta de conciliación | Ensayo sintético de reconciliación y restore, preservando origen y trazabilidad. La migración sigue bloqueando eventos sin hash; autorización separada antes de una base operacional. |
| Revisión independiente | Persona revisora de seguridad/producto | Candidato, diff, matriz de riesgos y evidencias | Revisión escrita de privacidad, permisos, integridad y restricciones; discrepancias resueltas y alcance aceptado. |

Para custodia no basta otro endpoint de la misma aplicación ni un archivo administrado con sus mismas credenciales. Elegir la solución concreta según independencia y requisitos aprobados; este plan no presupone una cuenta cloud, WORM/TSA ni proveedor específico ya operativo.

El mandato permite declarar riesgo y mantener una operación bloqueada en determinados casos, como purga. El informe vigente exige además evidencia externa de custodia. Antes de usar una excepción de cierre, dejar por escrito qué criterio se modifica y quién lo acepta; no convertir la falta de evidencia en un cumplido.

### Etapa 5 — Cierre documental y aceptación

Responsables: ingeniería, persona revisora independiente y titular. Dependencias: etapas anteriores según alcance aprobado.

1. Completar la matriz S2-01…13 con reproducción/condición inicial, código final, prueba, entorno, resultado, riesgo residual y enlaces. Distinguir VERIFICADO-CERRADO, MITIGADO y PENDIENTE; no confundir commit existente con aceptación.
2. Actualizar el informe de cierre y manuales sobre el candidato definitivo; corregir contradicciones de HMAC y disponibilidad Docker, referencias/duplicaciones del ADR y mensajes de producto sobre resultados oficiales, secreto o sellado. Si un texto está en una ruta excluida, registrarlo para una corrección de alcance separada.
3. Adjuntar manifiesto de artefactos con SHA del candidato, comandos, versiones, fechas, resultados, omitidos, digest y ubicación de evidencia sin secretos. Verificar que manifiesto y blobs seleccionados/commiteados coinciden; si cambia el código, repetir los controles afectados y ejecutar CI sobre el nuevo SHA.
4. Entregar PR revisable contra la rama de desarrollo pertinente, sin fusionar automáticamente a `main`. Registrar decisiones de alcance, restricciones y aceptación independiente.
5. Mantener NO-GO ante requisitos obligatorios ausentes. Solo emitir cierre del alcance expresamente aprobado cuando sus condiciones se cumplan; el secreto electoral y G1 conservan su gobierno separado.

Criterio de salida: evidencia completa del SHA final, matriz sin cierres ficticios, revisión independiente y decisión escrita coherente con la DoD vigente.

## 5. Cobertura de todos los hallazgos originales

Esta matriz asigna cada hallazgo a su ruta de cierre; no reemplaza la matriz de resultados que se completará al ejecutar.

| ID | Situación a resolver | Etapas | ¿Qué necesita? |
|---|---|---|---|
| S2-01 | Unicidad en tratamiento PII masivo | 0, 2, 5 | Código y pruebas locales/PG; decisión operativa antes de datos reales |
| S2-02 | Denominador familiar después de PII | 0, 2, 5 | Snapshot y backfill PG sintético; acta antes/después |
| S2-03 | Vínculo identidad/selección en Vote | 5: riesgo residual | Fuera del sprint; ADR y eventual integración autorizada, no infraestructura de tests |
| S2-04 | Comisión sin asignación y aislamiento | 1, 2, 5 | Regresiones HTTP y dos colegios/elecciones; revisión independiente |
| S2-05 | Persistencia/exposición y entrega de credenciales | 3, 4, 5 | Implementación local, canal real y decisión de producto; mientras tanto bloqueo productivo |
| S2-06 | Congelamiento y snapshot reproducible | 0, 2, 5 | Código, migraciones y concurrencia PG |
| S2-07 | Identificadores residuales en derechos | 0, 3, 4, 5 | Decisión de alcance; corrección separada autorizada o aceptación formal de alcance reducido; sigue pendiente mientras se difiere |
| S2-08 | Referencia de retención y legal hold | 2, 4, 5 | Pruebas locales/PG y aprobación humana/jurídica |
| S2-09 | Serialización, integridad y purga de cadena | 0, 2, 4, 5 | PG, rol restringido, recuperación y tratamiento legacy; purga bloqueada mientras falten épocas/anclas |
| S2-10 | Custodia independiente | 2, 4, 5 | Verificador local y custodio externo con recibo/prueba independiente |
| S2-11 | CI, E2E y escáneres reales | 1, 2, 4, 5 | Correcciones locales, servicios de prueba y CI del SHA final |
| S2-12 | Redis, cookies, cabeceras y CSRF | 1, 2, 5 | Redis real, dos procesos y navegador; no requiere servicio cloud para probar |
| S2-13 | Coherencia documental y gobierno | 0, 5 | Documentos, matriz de evidencia y revisión humana |

## 6. Orden de trabajo y decisiones de cierre

Orden inmediato: **candidato sin HMAC coherente → configuración de pruebas y migraciones → laboratorio Docker completo → correcciones y evidencias → SHA final y CI → aceptación independiente**. Preparar en paralelo las propuestas de entrega, custodia y retención, sin activar servicios ni tratamientos operacionales por el solo hecho de aprobar este plan.

Se pueden cerrar ahora tareas de selección, código, pruebas, contratos y documentación, y después demostrar localmente PostgreSQL/Redis/Nginx/recuperación con recursos ya disponibles. Requieren dependencia externa la evidencia CI, la custodia independiente y la entrega real. Requieren decisión humana el alcance S2-07, retención/holds, conciliación legacy y aceptación final.

Estado al entregar este documento: **plan preparado; pendientes técnicos y externos sin ejecutar; Sprint 2 NO-GO**. No se han marcado hallazgos nuevos como cerrados ni usado los resultados locales anteriores para aprobar un candidato que todavía no existe.
