# Sprint 3 — Estado de integración

**Fecha:** 2026-10-29, Chile. **Estado:** INTEGRADO A MAIN Y PROBADO LOCALMENTE. Cierre técnico: [informe](../remediacion/08-informe-sprint3-cierre.md). CI externa bloqueada por facturación; aceptación M1/M2 pendiente.

La integración se realizó por PR #10 en `f2f87dc918f4c25aff28165a3876519f03aa35f3`: 213 backend, 9 E2E reales y 5 contratos UI aprobados. Los PR 1–9 quedaron cerrados como sustituidos. La [evidencia de main](evidencias/main-validacion.json) conserva el SHA probado. El contenido siguiente se retiene como registro del candidato previo a publicación, no como estado de trabajo pendiente de fusión.

> Continuación autorizada: el titular solicitó integrar a `main`, probar y cerrar. El [procedimiento y alcance vigentes](integracion-main.md) distingue el cierre técnico de integración de la aceptación operacional. La suite conjunta ampliada pasó 213 casos sin fallos ni omisiones, incluidas actualizaciones desde S2-B/ADR aplicados y arranque sin DDL. Las referencias de publicación y ejecución de `main` se comprueban aparte de este corte previo.

La continuación se ejecuta en la rama `feat/sprint3-integration`, worktree `C:\Users\osval\AppData\Local\Temp\theogen-electoral-sprint3`, sobre `d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9` con cambios sin commit. Los resultados corresponden a ese árbol y a los archivos del [manifiesto](evidencias/candidato.json), no a un SHA futuro ni a `main`.

## Resultado de esta continuación

- Se retomó el candidato existente sin copiarlo sobre el árbol original de Sprint 2. Antes de esta entrega, las 70 rutas del inventario original conservaron sus SHA-256.
- Se corrigió la prueba HTTP con dos procesos para exigir el límite real de diez solicitudes compartidas, comprobar el contador Redis y verificar HTTP 503 durante la caída del servicio sintético. No se redujo el umbral de la aplicación.
- La emisión y la conciliación MVP bloquean y refrescan primero la elección; después bloquean al elector y, para conciliar, la operación. Rechazan estado electoral obsoleto y operaciones rechazadas sin enviar ni activar otra credencial. La activación confirmada deja un evento de auditoría en su misma transacción.
- Se añadieron regresiones de estado obsoleto y se amplió la restauración a datos no vacíos de vínculos, representantes, operaciones Belenios `UNKNOWN` y entregas MVP pendientes, además de votos/derechos históricos.
- El E2E usa una base nueva, credenciales sintéticas efímeras, puertos propios y servidores nuevos. Comprueba login/logout, cookies HttpOnly, CSRF aun con Bearer, comisión sin asignación/fuera de ámbito, padrón Belenios apagado, sufragio familiar, revocación de la otra credencial, cierre, participación del 50% y PDF.
- El workflow reúne la integración obligatoria, los E2E, escáneres y validación Compose/Nginx. No permite que los tests obligatorios pasen mediante skips; no reintenta automáticamente el E2E con mutaciones. Su ejecución remota sigue pendiente.
- Se revisaron las 41 coincidencias iniciales de Gitleaks: UUID de tests, un SHA documental y hashes/credenciales públicas del archivo electoral. Las ocho excepciones combinan ruta y valores exactos; no excluyen directorios ni archivos completos. Una clave aleatoria nueva en una de esas mismas rutas fue detectada.
- El entorno virtual contenía `python-jose`/`ecdsa` sin uso por el candidato, además de herramientas antiguas. Se retiraron esos dos paquetes únicamente del entorno aislado y se actualizaron pip/setuptools. Las dependencias directas instaladas coinciden con los pins del backend. No se modificó el entorno virtual de Sprint 2.

## Verificación local

La evidencia resumida y sus hashes se conservan en [validacion-local.json](evidencias/validacion-local.json). Los JUnit y reportes íntegros permanecen en directorios ignorados; no publicar fixtures con tokens, dumps, trazas ni correspondencias privadas.

| Control | Resultado | Límite |
|---|---|---|
| Backend | 213 aprobados, 0 fallos, 0 omitidos | PostgreSQL 16/Redis 7 locales y datos sintéticos; no CI remota |
| Auditoría | 100 eventos desde dos procesos; rol no propietario; UPDATE/DELETE rechazados | No acredita custodia administrativa independiente |
| Redis/HTTP | Contador compartido y rechazo durante caída | Fallo inducido solo en el contenedor etiquetado `sprint3-local` |
| Restore | Igualdad de las 13 tablas comparadas, con gestión Belenios y entregas no vacías | No restaura el almacenamiento de una urna Belenios real ni configura continuidad del piloto |
| E2E Chromium/HTTP | 9 aprobados, 0 reintentos | Backend y PostgreSQL reales; modo Belenios apagado; limitador en memoria para este recorrido de prueba |
| UI Belenios | 5 aprobados | API simulada; no se repitieron urnas del PoC ni votos de elecciones anteriores |
| Migraciones | Un head: `s3002_delivery`; instalación vacía, backfill poblado y actualización desde S2-B/ADR aplicados; downgrade destructivo rechazado | Datos sintéticos; migración y restore de datos operacionales requieren su procedimiento |
| Arranque de release | 5 escenarios POSIX aprobados; API productiva sin DDL y comando de migración separado | La provisión de identidades limitadas en el destino sigue pendiente |
| Frontend | Lint/build aprobados | Persisten advertencias de lint, props antiguas de MUI y tamaño del bundle |
| Dependencias | pip-audit del entorno aislado: sin vulnerabilidades conocidas; npm audit: 0 | Resultado fechado, no garantía permanente; transitivas backend aún sin lockfile completo |
| Secretos | Gitleaks 8.28.0: 0 hallazgos tras excepciones; control negativo detectado | Escaneo del contenido publicable actual; historial Git pendiente de ejecutar en CI |
| Operación | Compose válido; `nginx -t` aprobado con resolución del upstream | No prueba DNS/TLS del destino ni un despliegue productivo |

## Estado del backlog

| ID | Estado actual | Trabajo pendiente para aceptación |
|---|---|---|
| S3-00 | Candidato aislado y manifiesto disponibles | Revisar selección completa y confirmar decisiones de alcance; no se declara aceptada una reducción de S2-07 |
| S3-01 | Cabezas reunidas; matriz local vacía/S1/S2-B/ADR y restore aprobados; migración separada del arranque | Provisión del rol migrador y rol app en el destino; no se reescribieron funcionalmente e5/f6 publicadas |
| S3-02 | Workflow y controles locales preparados | Run remoto del candidato final, reglas de rama y revisión de permisos; bloqueo de cuenta descrito por el plan no comprobado de nuevo en esta continuación |
| S3-03 | Contratos por motor y entregas persistidas probados localmente | Entrega externa y recuperación real de la clave HMAC; revisar retención de correspondencias Belenios; aceptación del alcance completo S2-07 |
| S3-04 | Concurrencia, rollback y protección local comprobados | Recibo y verificación por custodio independiente; la purga permanece bloqueada |
| S3-05 | Configuración de piloto, TLS/destinos y controles probados con dobles | El colector/worker es un prototipo sin validación de despliegue, cuotas y aislamiento completo; faltan manifiestos, imágenes/configuración revisadas y prueba fuera del PoC |
| S3-06 | Pendiente | Autenticación/alias operativos, canal, autoridad, custodios y ceremonia independientes |
| S3-07 | Dashboard y expediente agregados implementados; pruebas locales | Actas y reglas institucionales, calendario, límite de 100 unidades y recorrido Belenios real |
| S3-08 | Suite integrada local y E2E MVP aprobados | Proveedor Belenios real del candidato final, todas las rutas de actualización, fallo/restore conjunto y verificación independiente |
| S3-09 | Informe de avance disponible | Candidato final publicado, CI verde y revisor independiente antes del PR/fusión final |
| S3-10 | Sin activar | Destino y responsables confirmados, G2/G3 y ensayo; G4 tiene aceptación separada |

M1 conserva sus criterios externos: CI del SHA final, revisión y controles independientes. La integración a `main` fue autorizada por el titular y se registra por separado de la aceptación operacional. M2 sigue pendiente: no se inició un piloto ni se enviaron correos; no se incorporaron participantes reales ni se modificó una elección previa. Este informe conserva el corte de pruebas previo a la publicación.

## Reproducción

Desde el worktree de Sprint 3, con su entorno virtual y los dos contenedores locales etiquetados:

```powershell
.\.venv\Scripts\python.exe scripts/verify_s3_local.py --postgres-container theogen-s3-20261029-pg --redis-container theogen-s3-20261029-redis --output .runtime/s3-integration.json
.\.venv\Scripts\python.exe scripts/verify_s3_e2e.py --postgres-container theogen-s3-20261029-pg
```

Cada ejecución crea bases nuevas; no dirigir estos runners a datos operacionales. El ensayo de Redis detiene y vuelve a iniciar únicamente su contenedor sintético. Las bases resultantes se conservan localmente para inspección; no se eliminaron bases previas ni volúmenes del PoC.

La configuración de excepciones sigue el contrato de [Gitleaks 8.28.0](https://github.com/gitleaks/gitleaks/blob/v8.28.0/README.md#configuration): reglas predeterminadas conservadas y coincidencia conjunta de ruta y valor. No se desactivó la detección genérica de API keys.
