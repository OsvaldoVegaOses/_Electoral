# CPA IAC: contexto de desarrollo y decisiones pendientes

Actualizado el 2026-10-30 a partir de la sintesis documental aportada por el titular. El agente no ha inspeccionado el ZIP ni los originales y no atribuye verificacion directa a esa sintesis. Los quince audios descritos no fueron transcritos en la revision aportada. Perfil estructurado: [case-cpa-iac.json](../../automation/sprint3/case-cpa-iac.json).

## Reglas que orientan la simulacion

| Materia | Antecedente reportado | Tratamiento de desarrollo |
|---|---|---|
| Voto | Art. 17 de 2022: uno por familia | Una unidad, un representante acreditado y una credencial privada Belenios por familia; la otra persona de la familia no recibe otra credencial |
| Candidaturas | Art. 23 modificado en 2026: individuales; Presidente por mayoria | No reutilizar listas de 2024; mantener pendiente la asignacion exacta de los demas cargos y los empates |
| Candidatos | Art. 24 modificado: inscripcion vigente, dos anos activos, cuotas al dia y otros requisitos | Etapa de admisibilidad, observaciones y resolucion antes de publicar candidaturas definitivas; el texto integro debe revisarse |
| Comite | Art. 51: cinco miembros, un ano minimo, incompatibilidad con directivo actual o candidato | Cinco propuestas, sin constitucion formal acreditada; no aplicar automaticamente los requisitos de candidatos al Comite |
| Asamblea | Art. 18: 25% de socios en primera citacion y regla de segunda citacion | Distinguir quorum de constitucion de Asamblea del umbral de participacion de la eleccion. No completar la segunda citacion sin el texto aplicable |
| Cuotas | La Directiva solicita verificar pagos de voluntarios | No convertir esa solicitud en una exclusion automatica de electores; pendiente precisar fundamento y alcance institucional/juridico |

El apoyo interno a proponer el 3 de noviembre de 2026 a las 18:00, America/Santiago, no constituye convocatoria formal, ratificacion del Comite ni aprobacion de una eleccion electronica. La plataforma no programa esa Asamblea ni la presenta como confirmada.

## Decisiones externas

Permanecen pendientes la constitucion formal del Comite, bases electorales, modalidad electronica, politica R1/R2, blancos/nulos, empates y asignacion de cargos; autoridad de credenciales, custodios y revisor independiente; y aceptaciones G2/G3/G4. Las cinco personas propuestas no asumen automaticamente esas autoridades. La participacion del desarrollador u operador en la organizacion exige una verificacion que no dependa exclusivamente de el.

## Privacidad

No incorporar el ZIP, nombres de los voluntarios, RUT, correos, datos de estudiantes ni pagos a Git, fixtures o urnas de prueba. El desarrollo utiliza familias y personas ficticias. La lista nominal no es necesaria para implementar ni probar estos contratos; su eventual registro operacional requiere el procedimiento y acceso correspondiente.
