# Sprint 3: matriz vigente de aceptacion

Fecha: 2026-10-30. Esta matriz y los informes de ejecucion sustituyen estimaciones porcentuales. Un resultado tecnico integrado no acredita aceptacion institucional, independencia o eleccion vinculante.

| Frente | Evidencia disponible | Trabajo restante | Responsable de aceptacion |
|---|---|---|---|
| Integracion S1/S2/ADR | PR 10, 11 y 12 integrados en main; un head Alembic, instalacion y actualizaciones probadas | Conservar evidencia del SHA evaluado y revisar cada cambio posterior | Ingenieria; revision independiente M1 pendiente |
| CI | Azure ACR ch1f Succeeded sobre codigo desplegado 49efa08: 213 backend, 9 E2E, 5 UI con dobles | Validar cada candidato nuevo; GitHub Actions conserva bloqueo de facturacion | Controlador tecnico y revisor |
| Privacidad y derechos | HMAC completo, retencion/hold, denominadores y regresiones integrados | Ensayo de recuperacion de clave, revision de correspondencias, backups y tratamiento institucional | Ingenieria, responsable de datos y revisor |
| Secreto del voto | Belenios experimental separado del motor MVP | Recorrido real Belenios del destino, custodia y verificacion independientes. La correlacion historica voter_id/candidate_id del MVP permanece | Autoridades electorales y auditor |
| Auditoria | Concurrencia, cadena, rollback y rol no propietario probados | Checkpoints, recibos y recuperacion por custodio externo | Custodio y revisor independientes |
| Instancia Azure | HTTPS, PostgreSQL persistente Entra, Redis, admin y sesiones verificados | Continuidad, monitorizacion, salida de red estable y recuperacion electoral conjunta; la prueba no certifica esas capacidades | Operacion |
| Verificador y runtime | Prototipo de colector/worker y validaciones de piloto | Aislamiento, cuotas, reclamacion atomica, manifiesto, ensayo fuera del PoC y nueva urna sintetica | Ingenieria y operador de destino |
| Credenciales e identidad | Contratos separados por motor y estados de entrega persistidos | Canal controlado, entrega/recuperacion de destino y autoridad ajena al administrador | Autoridad de credenciales |
| CPA IAC | Sintesis aportada por el titular: voto familiar, candidaturas individuales, requisitos diferenciados y cinco propuestas de Comite | Revisar originales, formalizacion del Comite, bases, electronica, R1/R2 y restantes reglas | Institucion y responsable juridico |
| Simulacro | E2E MVP y pruebas tecnicas disponibles | Ensayo Belenios de destino con carga, entrega, incidentes, cierre, escrutinio y restore coordinado | Comision, operacion, custodios y auditor |

## Etapas y criterio de paso

- M1: evidencia tecnica del candidato exacto, pendientes S2 cerrados o alcance expresamente aceptado y revision independiente. La automatizacion puede integrar codigo tecnico, no firmar esa revision.
- M2/G3: M1, politica institucional aplicable, destino y entrega verificados, autoridades separadas, simulacro y aceptacion del piloto. La configuracion production y la existencia de un administrador no habilitan participantes reales.
- G4: aceptacion formal de la primera eleccion vinculante, con sus reglas, revision y responsables. No se deriva de porcentajes ni de una encuesta interna.

## Ejecucion autonoma

La [cola de desarrollo](../../automation/sprint3/queue.json) contiene diez tareas tecnicas y cinco gates externos. El [caso CPA IAC](caso-cpa-iac.md) es el primer trabajo. Estado y evidencia por ciclo: `.runtime/autonomy/state.json`, `.runtime/autonomy/latest.json` y `.runtime/autonomy/runs/`. Los informes privados no se publican automaticamente.

Los documentos anteriores conservan sus cortes historicos. Las pruebas de otro SHA, datos sinteticos, dobles y despliegue de prueba se identifican por su alcance; ninguna de ellas sustituye el ensayo electoral ni la aprobacion externa.
