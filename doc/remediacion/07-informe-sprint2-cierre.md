# Informe de cierre Sprint 2 — S2-C, S2-D y S2-E

> Actualización 2026-10-29: el candidato aislado de Sprint 3 ya ejecutó PostgreSQL 16, Redis 7, concurrencia, restore y E2E con los resultados del [informe vigente](../Sprint_3/estado-implementacion.md). Las limitaciones que siguen describen el corte histórico de este informe. M1/M2 y la custodia independiente permanecen pendientes; no se declara cerrado Sprint 2 por estas pruebas locales.

**Estado global: NO-GO.** Hay implementación y evidencia local, pero faltan validaciones obligatorias en PostgreSQL 16, ejecución de los gates en CI y custodia externa verificable de checkpoints. Este informe no declara el sprint cerrado ni apto para producción.

## Resumen ejecutivo

| Frente | Estado | Motivo |
|---|---|---|
| S2-C — privacidad y credenciales | Implementado con restricciones operacionales | HMAC separado y backfill implementados; anonimización respeta retención y legal hold. Sin canal real de entrega, las operaciones de credenciales siguen bloqueadas en producción. La migración con datos debe validarse en PostgreSQL 16. |
| S2-D — auditoría | Parcial; bloqueado | Existe serialización de escritores, verificación y exportación de checkpoints. No se ha ejecutado la prueba de concurrencia en PostgreSQL 16 ni se ha acreditado custodia independiente. |
| S2-E — calidad y operación | Gates configurados; evidencia externa pendiente | Suite backend, Playwright, lint, build y migraciones SQLite locales pasaron. No hay resultado de CI remoto y Docker no está disponible para validar Compose, Nginx y backup/restore localmente. |

## Evidencia ejecutada

| Validación | Resultado | Alcance y límites |
|---|---|---|
| Pruebas focalizadas de backfills/migraciones | **4 passed** | Ejecutadas localmente sobre SQLite; no acreditan backfill ni rollback PostgreSQL. |
| Suite backend completa | **136 passed, 8 skipped** | Ejecución local. Los skips de servicios/URLs no sustituyen los gates reales. |
| Playwright Chromium | **7 passed** | Ejecución local con base SQLite sintética temporal; no equivale a evidencia del job CI con PostgreSQL 16. |
| Alembic upgrade → downgrade base → upgrade head | **Correcto** | PostgreSQL no disponible; la secuencia se ejecutó sobre SQLite vacío. No valida backfill ni rollback con derechos existentes. |
| Frontend lint | **Correcto con advertencias** | Advertencias preexistentes de lint; no se corrigieron por estar fuera del alcance. |
| Frontend build | **Correcto con advertencia** | El bundle principal supera 500 kB. |
| `git diff --check` | **Correcto** | Sin errores de whitespace. |
| Parseo YAML del workflow | **Correcto** | No reemplaza una ejecución real de GitHub Actions. |
| CI remoto, PostgreSQL 16, Redis real, Nginx y backup/restore | **No ejecutados** | Docker local no está activo; no se dispone de una ejecución CI asociada a estos cambios. |

## S2-C — privacidad, derechos y credenciales

- `ENTITLEMENT_HMAC_KEY` es una clave persistente separada, con mínimo de 32 bytes; `unit_key` se deriva como HMAC contextual y opaco.
- El backfill exige la clave antes de modificar derechos existentes. El downgrade con datos no es reversible y requiere restaurar un backup protegido anterior.
- La elegibilidad para anonimización requiere una fecha de cierre verificable, vencimiento de retención y ausencia de `legal_hold`. La vía manual aplica los mismos controles.
- Las altas, importaciones, reemisiones y apertura que depende de credenciales quedan bloqueadas en producción mientras no exista un canal real de entrega. No se deben exponer credenciales ni habilitar elecciones productivas antes de resolverlo.
- La purga física de auditoría queda bloqueada con HTTP 409. `dry_run=true` cuenta candidatos sin borrar; falta diseñar retención por épocas y verificar checkpoints externos.
- El denominador electoral usa la instantánea congelada S2-B. Esto no resuelve el riesgo de correlación entre `Vote.voter_id` y `candidate_id`; no se afirma secreto del voto.

**Pendiente para aceptar S2-C:** ejecutar upgrade, backfill con datos sintéticos, verificación de denominadores, downgrade seguro y upgrade de nuevo sobre PostgreSQL 16; demostrar que la clave se provisiona, respalda y restaura de forma persistente; implementar y probar un canal de entrega antes de habilitar credenciales en producción.

## S2-D — cadena de auditoría

- Las escrituras coordinan el head compartido en PostgreSQL dentro de la transacción del evento; rollback revierte el evento y el head.
- Hay verificación local de cadena y generación/verificación de artefactos de checkpoint.
- El estado de la API permanece `PENDIENTE_ANCLAJE_EXTERNO` y `independent_custody_confirmed: false`. Un checkpoint local no prueba custodia, no repudio ni anclaje externo.

**Bloqueos:** correr la prueba de 100 escritores independientes y rollback en PostgreSQL 16; obtener un recibo verificable de un custodio independiente y demostrar la verificación posterior del artefacto. Hasta entonces S2-D no se cierra.

## S2-E — gates y operación

El workflow configura suite backend y upgrade/downgrade/upgrade de migraciones vacías con PostgreSQL 16, lint/build, Playwright, escaneo de secretos/dependencias, validación Compose/Nginx y backup/restauración. El paso de restauración solo se ejecuta tras éxito del backup, y el apagado del servicio de pruebas conserva `if: always()`. El flujo vacío no demuestra el backfill ni un rollback con derechos existentes.

Los resultados locales de este informe no son una ejecución de GitHub Actions. Debe obtenerse un run exitoso del workflow completo en la rama/PR. También deben conservarse los artefactos/logs de CI, Playwright y restauración como evidencia.

## Criterios de salida antes de declarar GO

1. CI verde con PostgreSQL 16; añadir/evidenciar migración y backfill con datos sintéticos, estrategia segura de rollback y concurrencia de auditoría.
2. Playwright y gates de seguridad/build aprobados en CI.
3. Compose y Nginx validados; backup con checksum y restauración comprobada con registros sintéticos.
4. Evidencia de custodia independiente del checkpoint y verificación posterior contra la cadena.
5. Clave HMAC de derechos provisionada y respaldada fuera de la base; procedimiento de recuperación ensayado.
6. Canal real de entrega de credenciales implementado antes de habilitar altas o reemisiones en producción.
7. Revisión jurídica de períodos de retención y aprobación de legal holds; riesgo de secreto del voto resuelto o explícitamente aceptado fuera de este alcance.

**Conclusión:** mantener el estado **NO-GO** hasta completar y adjuntar esas evidencias. No interpretar pruebas locales en SQLite como certificación de PostgreSQL 16 ni el checkpoint exportado como anclaje externo.

## Actualización de implementación local — 2026-10-28

Esta sección reemplaza los recuentos locales anteriores; refleja el worktree actual, no un commit publicado ni un run de CI.

| Validación | Resultado | Alcance y límites |
|---|---|---|
| Suite backend completa | **136 passed, 8 skipped** | SQLite/local. Los escenarios PostgreSQL/Redis real quedan en CI y no se ejecutaron aquí. |
| Backfills y migraciones focalizados | **4 passed** | SQLite; no sustituye la validación con PostgreSQL 16. |
| Alembic upgrade → downgrade base → upgrade head | **Correcto** | Base SQLite temporal, sin datos operacionales. |
| Playwright Chromium | **7 passed** | SQLite y credenciales sintéticas de prueba; no equivale al gate CI con PostgreSQL. |
| Frontend lint/build | **Correctos con advertencias** | Se mantienen advertencias de lint y tamaño del bundle. |
| Compose, YAML del workflow y `git diff --check` | **Correctos** | Validación de configuración local; no ejecuta servicios ni workflow remoto. |

Se actualizaron textos de la interfaz y la vista previa de correo para no afirmar secreto criptográfico, auditoría independiente, sellado verificable ni carácter oficial de los resultados. Belenios y la estructura criptográfica de `Vote` no se modificaron. Sin embargo, sí hay cambios en la ruta `backend/app/routers/voting.py` y en la provisión de derechos al abrir elecciones: ahora derivan `unit_key` con HMAC. Por ello, no es correcto afirmar que el motor/ruta de votación quedó intacto. Los mensajes de esa ruta que califican el sufragio como “irreversible” o “sellado” tampoco se cambiaron, para respetar el límite de alcance.

La migración de la cadena de auditoría falla deliberadamente si encuentra eventos legacy sin hash: no se debe ejecutar sobre datos operacionales hasta aprobar y ensayar una reconciliación respaldada. No se hicieron commit ni push. **El estado continúa NO-GO** hasta tener CI verde en el SHA publicado y resolver los criterios de salida de S2-C/D/E indicados arriba.

## Preparación de decisión: límite de alcance y evidencia externa

### Frontera entre Sprint 2 y la ruta de votación

El inventario actual contiene **51 paths**: 46 asociados al trabajo de Sprint 2, 2 documentos del PoC y 3 resultados de Playwright. Los 2 documentos del PoC y los resultados generados quedan fuera de un commit de cierre del sprint. `doc/motor/propuestas_motor.md` no aparece modificado.

La parte que cruza el límite acordado de “no tocar el motor” es un conjunto funcional, no un único archivo:

| Componente | Cambio relacionado | Dependencia |
|---|---|---|
| `backend/app/routers/voting.py` | Deriva la clave HMAC que se busca al validar y consumir un derecho de sufragio. | Debe generar la misma clave que la apertura; afecta validación y emisión de voto, aunque no cambia `Vote` ni su criptografía. |
| `backend/app/routers/elections.py` | Deriva claves HMAC al provisionar derechos durante apertura. También contiene, en hunks separados, el bloqueo de apertura por falta de canal de entrega. | La derivación debe corresponder con el algoritmo de la ruta y con los valores persistidos. El bloqueo de entrega es independiente y puede revisarse aparte. |
| `backend/app/entitlements.py` y `ENTITLEMENT_HMAC_KEY` en `config.py` | Algoritmo y configuración del secreto que produce las claves opacas. | Sin clave estable, las claves calculadas no coinciden entre reinicios/instancias. |
| `b2c3d4e5f6a7_hmac_voting_entitlements.py` | Reescribe los `unit_key` existentes a HMAC; no tiene downgrade reversible si ya hay claves HMAC. | Debe desplegarse coordinadamente con el algoritmo de lectura y con respaldo/recuperación de la clave. |
| Modelo, Compose, workflow y pruebas de migración | Documentan/configuran la clave y verifican backfill/compatibilidad. | Requieren selección por hunk: contienen también cambios independientes de Sprint 2. |

**Decisión de alcance confirmada:** diferir la transformación HMAC de `unit_key` y excluir el paquete completo del cierre Sprint 2 para respetar la restricción de no tocar el motor. No incluir solo la migración sin el lector, ni solo el lector sin migración: ambos lados deben permanecer compatibles. El trabajo queda en el árbol de trabajo para una revisión futura; no se elimina ni se incluye en el cierre selectivo. S2-C queda **parcial** en privacidad de derechos electorales y no se debe afirmar que `unit_key` ya está anonimizado.

La selección del cierre deberá conservar únicamente los hunks independientes de `backend/app/routers/elections.py`, `backend/app/config.py`, `backend/app/models.py` y `.github/workflows/ci.yml`. También deberá excluir la migración HMAC, su helper y pruebas exclusivas, y retirar o separar la aserción/fixture PostgreSQL que solo valida ese backfill. Esto es una guía para revisión selectiva; **no se ha hecho staging ni se ha alterado ningún hunk**.

### Evidencias que faltan para una aceptación auditable

| Evidencia | Entregable aceptable | Estado / condición de cierre |
|---|---|---|
| CI del alcance seleccionado | URL del run de GitHub Actions y SHA exacto; jobs requeridos verdes; artefactos sin secretos ni PII. | Pendiente. Ejecutar solo después de cerrar la selección de alcance; el SHA probado debe coincidir con el revisado. |
| PostgreSQL 16 y Redis | Logs/artefactos CI que demuestren migración vacía, backfill sintético, rollback/upgrade, concurrencia de auditoría y rate limiting con Redis real. | Pendiente; los **136 passed, 8 skipped** son ejecución local y no reemplazan esos servicios. |
| Playwright | Run identificable en CI con login, CSRF y flujo autorizado; report HTML/JUnit y capturas sanitizadas si falla. | Pendiente de evidencia reproducible. El `.last-run.json` que hoy permanece en `frontend/test-results/` registra una ejecución fallida en login (`Correo o contraseña incorrectos`), por lo que esos tres artefactos no demuestran aceptación. El registro previo de **7 passed** debe repetirse sobre el SHA final. |
| Operación y restauración | Job exitoso de `nginx -t`, Compose, backup con checksum y restauración de registros sintéticos comprobada. | Pendiente de ejecución real; la inspección de configuración local no basta. |
| Custodia del checkpoint | Artefacto con digest, head/secuencia, conteo y timestamp; recibo del custodio independiente/WORM/TSA y verificación repetida por un tercero. | Pendiente. Un checkpoint generado o alojado por la misma aplicación no es evidencia independiente. |
| Claves HMAC (si se aprueba incluir ese paquete) | Evidencia redactada de provisión persistente, respaldo protegido y ejercicio de recuperación que confirme que la clave restaurada reproduce los mismos identificadores. No adjuntar el secreto. | Pendiente y bloqueante para desplegar esa migración; no forma parte del cierre estricto mientras el paquete se difiera. |
| Credenciales | Diseño aprobado y prueba del canal real de entrega, reemisión, fallo/reintento y revocación; no registrar tokens en artefactos. | No implementado. Mantener fail-closed en producción; no es sustituible por evidencia de CI. |
| Datos legacy de auditoría | Inventario sintético/anonimizado, backup protegido, procedimiento de reconciliación aprobado y ensayo de restore/reconciliación antes de cualquier base operacional. | Pendiente. La migración debe seguir bloqueando ante eventos sin hash hasta completar este gate. |
| Retención y legal hold | Decisión jurídica/documentada sobre plazos por tipo de dato y responsables autorizados para activar/liberar hold. | Pendiente de aprobación; no inferir plazos legales desde defaults técnicos. |

### Caveats de las validaciones locales

- `pytest tests -q` pasó con **136 passed, 8 skipped**. Los skips de dependencias externas no son aprobaciones de esos gates.
- `pytest -q` desde `backend` falla en `test_setup.py::test_everything` cuando usa un SQLite local con esquema previo (`no such column: users.school_id`). Ese script también imprime el token del primer elector; no usar su salida como evidencia y corregirlo o mantenerlo fuera de las suites ejecutables antes de ampliar el comando de CI.
- El fallo de Playwright conservado corresponde a un login que no alcanzó `/` porque el backend rechazó las credenciales de prueba. Hasta reproducir y pasar el flujo con fixtures deterministas, no considerar sus artefactos como evidencia positiva.
- No se ha hecho `git add`, commit, push ni cambio en `doc/motor/` o Belenios.

**Siguientes gates:** (1) separar los hunks mixtos y materializar una selección que excluya el paquete HMAC de derechos; (2) obtener y enlazar las evidencias de la matriz en el SHA final; (3) conservar fuera del cierre los documentos del PoC y los artefactos generados de Playwright. La decisión de diferir el paquete HMAC queda resuelta; hasta completar los gates restantes, el cierre continúa **NO-GO**.
