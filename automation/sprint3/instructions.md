# Desarrollo autonomo de Sprint 3

El titular aprobo implementar el Sprint 3 de habilitacion electoral y automatizar su desarrollo. Trabaja SOLO en la tarea JSON que recibes, dentro del worktree asignado. Lee el codigo antes de proponer cambios. Implementa un resultado completo, pequeno y revisable con pruebas de comportamiento relevantes; no cierres una tarea por redactar un documento.

El caso de referencia es CPA IAC. Lee `automation/sprint3/case-cpa-iac.json` y `doc/Sprint_3/caso-cpa-iac.md`. Son antecedentes reportados por el titular, no originales inspeccionados por el agente ni aprobaciones institucionales. Usa candidaturas individuales, no listas de 2024; distingue Presidente de asignacion de otros cargos, quorum de Asamblea de participacion electoral, y requisitos del Comite de requisitos de candidatos. Una familia tiene un representante acreditado y una credencial Belenios. No excluyas electores automaticamente por cuotas ni asumas constitucion formal del Comite. No uses los nombres reales de los cinco propuestos.

No hagas commit, push, merge ni crees PR: el controlador ejecuta esos pasos despues de comprobar rutas y CI real. No alteres CI, escaneres, tests existentes, esta automatizacion, su cola ni sus limites. Puedes anadir los tests nuevos previstos en el alcance. No leas el directorio `.runtime` del checkout original, archivos privados de despliegue, credenciales ni almacenes de claves. No publiques logs, dumps o fixtures con tokens. No uses agentes adicionales.

Conserva el soporte del motor MVP y la separacion por motor; HMAC es seudonimizacion y la correlacion historica `Vote.voter_id/candidate_id` no queda resuelta por otra funcion. Belenios sigue apagado en el destino Azure. No envies correos, no incorpores electores reales, no cambies roles/cloud/redes/servicios desplegados ni reutilices las urnas del PoC. Usa datos y servicios sinteticos nuevos con nombres y etiquetas propios.

No inventes la institucion, estatutos, autoridades, custodios, claves externas, aprobaciones G2/G3/G4 ni revision independiente. Implementa y prueba los contratos tecnicos que puedan prepararse sin esas decisiones; registra los requisitos externos que permanecen pendientes. Que una tarea este integrada tecnicamente no significa aceptacion electoral.

Nunca reintentes una mutacion remota de resultado desconocido. Preserva intenciones y exige cotejo. No conviertas errores, falta de resultado, tests omitidos ni recibos propios en aprobaciones. No debilites asserts ni controles para conseguir un resultado verde.

Al finalizar escribe el resultado conforme al schema. `implemented` exige cambios funcionales y tests nuevos; `blocked` identifica informacion o capacidad realmente ausente. No afirmes que corrio una prueba que no ejecutaste. El controlador validara el commit completo en Azure; tus resultados no sustituyen esa verificacion ni una revision externa.
