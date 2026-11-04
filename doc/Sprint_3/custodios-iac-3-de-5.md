# Custodia CPA IAC: tres aportes entre cinco integrantes

El titular confirmó el 4 de noviembre de 2026 que los cinco integrantes del TRICEL serán los custodios y que el umbral será **3 de 5**. La designación y el umbral no equivalen a la generación de claves, aceptación individual ni independencia comprobada. El veedor externo sigue pendiente.

La preparación de una nueva vinculación debe registrar `trustee_policy: {"count": 5, "threshold": 3}` junto con la referencia de aprobación de la comisión. Se conserva esa política por elección, separada del JSON nativo enviado a Belenios. Antes de validar, el adaptador exige cinco custodios Threshold, umbral tres, credenciales y ceremonia listas, y padrón/papeleta coincidentes. La interfaz muestra la política registrada. El resultado agregado conserva la referencia y el umbral; no afirma custodia humana independiente.

La migración `s3003_trustees` agrega una columna nullable sin modificar UUID, padrón, ceremonia o archivos criptográficos. Las vinculaciones anteriores quedan sin política registrada: se bloquean su validación y apertura, sin atribuirles automáticamente 2/3 ni 3/5. No existe una ruta para cambiar la política de una vinculación ya preparada. El límite de nueve custodios es un límite de este adaptador; no una afirmación sobre la capacidad del motor.

## Ceremonia y escrutinio

1. Cotejar los cinco custodios, sus correos y la referencia del acuerdo, y documentar quién administra la urna y quién emite las credenciales.
2. Cada custodio genera y descarga su clave privada en su propio equipo, conserva un respaldo bajo su control y envía únicamente el material público mediante el flujo nativo. No entregar privadas al administrador ni a TheoGen.
3. Cotejar las cinco huellas y completar todos los pasos nativos antes de validar la elección.
4. Para el escrutinio se necesitan tres aportes externos válidos, además del componente del servidor exigido por la configuración nativa. Una reunión presencial facilita el acompañamiento; cada custodio opera su parte. Una aprobación digital o un acta no sustituye el aporte criptográfico.
5. Conservar acta y archivo público; un revisor independiente debe verificar el resultado con su propio entorno.

No modificar el borrador de ensayo existente para convertirlo automáticamente a 3/5: el último corte registrado tenía ocho entradas y umbral dos. Antes de cualquier reinicio o sustitución, cotejar el estado actual y acordar el tratamiento de ese ensayo. La implementación permite preparar una elección nueva con la política explícita; no reinicia ceremonias ni crea urnas operacionales por sí sola.

## Brechas que conservan su criterio de cierre

| Frente | Criterio pendiente |
|---|---|
| Candidaturas | Recepción individual con comprobante; revisión, observaciones, subsanación y resolución del TRICEL; nómina definitiva aprobada |
| Padrón familiar | Fuente aprobada, familias y duplicados cotejados; un representante y una credencial por unidad; capacidad y carga superiores al límite del piloto verificadas |
| Papeleta y reglas | Calendario, selección de cargos, empates, blanco/nulo y política de revoto aprobados; la integración actual solo modela una selección obligatoria |
| Correo | Cuenta TRICEL preparada y dominio autenticado; levantar bloqueo 403/1010 de las consultas desde la VM antes de activar el cambio global |
| Custodia | Ceremonia 3/5 con control individual real y prueba de ausencia; verificación de las diez combinaciones de tres custodios con datos sintéticos nuevos |
| Credenciales | Autoridad designada y canal separado; emisión, entrega y recuperación comprobadas sin duplicar el derecho familiar |
| Operación | Versión exacta, CI, backup/restore conjunto, cierre/escrutinio y comprobación independiente |
| Aceptación | Evidencia técnica revisada y aprobación de la configuración electoral concreta por el TRICEL |

Este documento registra la decisión 3/5 y el alcance técnico. No declara terminadas las otras brechas ni habilita una elección vinculante.
