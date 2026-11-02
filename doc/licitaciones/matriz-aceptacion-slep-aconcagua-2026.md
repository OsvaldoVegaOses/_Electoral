# Matriz de aceptación de referencia — SLEP Aconcagua, licitación 1375746-20-LE26

> **Estado: referencia externa / NO constituye oferta, postulación, aceptación contractual, certificación ni autorización de elección vinculante.**
>
> **Corte documental y de código:** 2026-11-02. Repositorio `_Electoral`, rama `main`, commit `808eb0351f46a5dd18b57ce00665e9d56106e3c7` (30-10-2026). Este archivo **complementa, no reemplaza**, la [matriz de aceptación vigente de Sprint 3](../Sprint_3/matriz-aceptacion.md) y sus compuertas M1/M2/G3/G4.

## 1. Propósito, fuentes y límites

Esta matriz transforma obligaciones de una contratación pública específica en **criterios de referencia para desarrollo y futura debida diligencia comercial**. No presupone que TheoGen Electoral participe o vaya a participar en la licitación ni que las condiciones de este proceso sean universales. No se han presentado ofertas, creado padrones reales, enviado credenciales a votantes ni habilitado elecciones oficiales como resultado de este documento.

**Fuentes primarias aportadas por el titular (no incorporadas al repositorio público):**

- `4-REX-SERVICIO-DE-ENCUESTAS.pdf` (70 páginas): resolución y bases administrativas/técnicas; SHA-256 `8aff72103fda128c1b0dbdf74a3cdd9c80cdc19e1edc2d6aaa06297dcea9a4b6` (**B**, páginas PDF 1–70).
- `1-PREGUNTAS-Y-RESPUESTAS-VOTO-ELECTRONICO.pdf` (20 páginas): aclaraciones oficiales de 28-10-2026; SHA-256 `3f009d3586ded90f7de2fc26553c65807b6e456955fd996d9e1331132417b1bb` (**Q**, preguntas 1–43).
- `2-ANEXOS_EDITABLES.docx`: formularios Anexos 1–5; SHA-256 `2e33fec865df195cc73e720f524ea9bd947e90467b6b6011b65dfa644d879067` (**A**).
- `3-Solicitud_compra_aprobada_INT-2026-00032_05-10-2026_(1).pdf`: antecedente de solicitud; SHA-256 `34f96f8be9ea0b7f58e0a03f36b2d825e6644d0fcf0061dcb10f0861eaf11792`.

Las citas `B p. N` señalan la página del PDF (no el índice de un extracto), y `Q N` la pregunta/respuesta oficial. No se redistribuyen adjuntos de la licitación ni datos personales en este repositorio público. Contrastar **siempre** con originales y eventuales modificaciones oficiales antes de usar la matriz en otro procedimiento.

### Tres niveles de evidencia, evaluados por separado

| Nivel | Pregunta | Estados permitidos | Regla de aceptación |
|---|---|---|---|
| **F — Funcionalidad desarrollada** | ¿Existe código que implemente el requisito completo, no solo una interfaz o una propuesta? | `I` implementada en código; `P` parcial/experimental; `ND` no demostrada; `—` no aplica a software | `I` exige rutas de código y revisión de limitaciones; no equivale a producción. |
| **V — Prueba verificable** | ¿Existe ejecución trazable sobre versión identificada, con datos y condiciones representativos? | `R` reporte de pruebas internas con alcance identificable; `L` laboratorio/sintéticos o prueba incompleta; `ND` sin prueba suficiente; `—` no aplica | `R` **no** significa auditoría independiente ni prueba reejecutada en esta revisión. Para aprobar contractual/operacionalmente se exige evidencia de destino, configuración y tercero según cada fila. |
| **X — Documento externo/contractual** | ¿Existe el documento firmado, emitido o validado por tercero/mandante/autoridad cuando corresponde? | `EX` externo verificado; `PE` pendiente/no aportado; `DI` solo documentación interna; `—` no corresponde | `DI` no sustituye `EX`. No se ha acreditado **ningún** `EX` con el material disponible. |

**Importante:** un `I` o `R` no autoriza pasar a elección vinculante. `ND` no declara ausencia absoluta: señala falta de evidencia suficiente en el código/documentos inspeccionados. Los estados son el diagnóstico de referencia de esta fecha; no reemplazan ejecución de CI, auditorías, pruebas de penetración ni validación del propietario del producto.

### Evidencia técnica existente y sus límites

- [Código de voto MVP](../../backend/app/routers/voting.py), [modelo relacional](../../backend/app/models.py), [padrones](../../backend/app/routers/voters.py), [escrutinio](../../backend/app/routers/reports.py), [seguridad](../../backend/app/auth.py), [configuración](../../backend/app/config.py).
- [Integración Belenios](../../backend/app/belenios/client.py), [configuración de piloto y comprobación de manifiesto](../../backend/app/belenios/deployment.py), [verificación](../../backend/app/belenios/verification.py), [informe ADR-001](../motor/implementacion_adr001.md) y [matriz Sprint 3](../Sprint_3/matriz-aceptacion.md).
- [Prueba Azure de la aplicación administrativa](../Sprint_3/despliegue-prueba-azure.md) y [estado de Sprint 3](../Sprint_3/estado-implementacion.md). Los informes del repositorio registran resultados en CI alternativo Azure; el último commit referencia **252 backend, 9 E2E y 5 UI**, pero corresponden a los escenarios definidos allí, no a una prueba pública de 20.000 electores ni a la aceptación externa de una elección. La instancia Azure de prueba usa recursos en EE. UU.; no acredita residencia nacional.
- La ruta MVP almacena selección vinculada a candidatura en la tabla `Vote` y su documentación vigente advierte que **no ofrece secreto criptográfico verificable**. Belenios está separado y requiere compuertas, custodia y aceptación independientes. [Documento de activación](../Sprint_3/activacion-belenios.md).

## 2. Matriz por requisito

**Interpretación:** `F`, `V` y `X` son juicios separados. La columna de aceptación describe la prueba o el antecedente **a obtener**, no afirma que ya exista. Los requisitos con constancias externas se evalúan aunque `F=—`.

### 2.1 Admisibilidad, documentación y condiciones de proveedor

| ID | Requisito y base | F | V | X | Evidencia / criterio objetivo de aceptación pendiente |
|---|---|:--:|:--:|:--:|---|
| AD-01 | **Mínimo 3 elecciones electrónicas ejecutadas** en 5 años y 1 con ≥5.000 habilitados. **B pp.59–60, n.23.1** | — | — | PE | Tres antecedentes atribuibles al oferente, con mandante, año, padrón y objeto; documentos de conformidad, OC, contrato o acta según numeral 23. No confundir pruebas sintéticas con experiencia ejecutada. |
| AD-02 | **Puntaje por experiencia**, distinto de admisibilidad. **B p.18, n.12.1.2; Q2; A4** | — | — | PE | Certificados de conformidad válidos, firmados, con RUT/contacto/periodo; Q2 precisa que para el criterio evaluado solo se aceptan certificados. No trasladar automáticamente la admisibilidad documental al puntaje. |
| AD-03 | **ISO/IEC 27001 vigente o certificación equivalente de tercero**, con alcance que cubra operación. **B p.60, n.23.2; Q1** | — | L | PE | Certificado vigente independiente, descripción de alcance, controles y, si es equivalente, informe que sustente equivalencia. Q1 admite certificado de empresa externa, pero **no convierte test internos en certificación**. |
| AD-04 | **Arquitectura demostrable de secreto y custodia distribuida** como requisito técnico del oferente. **B p.60, n.23.3; Q14** | P | L | PE | Arquitectura firmada/revisada, ensayo con autoridad independiente y prueba de que el operador no puede descifrar unilateralmente. Q14 permite alternativas justificadas. |
| AD-05 | **Dotación y plan de soporte territorial**. **B pp.47,60, n.12.4/23.4; Q8–Q11** | — | ND | PE | Plan, responsables, turnos, canales y medios verificables. La aclaración permite soporte remoto especializado equivalente, **no elimina los SLA**. |
| AD-06 | **No inhabilidades para contratar; declaración jurada**. **B pp.59–60, n.23.5; A2** | — | — | PE | Verificación jurídica actual, habilitación como proveedor, declaración Anexo 2 completa y firmada. Nunca autogenerar una declaración de veracidad sin revisión del titular. |
| AD-07 | **Identificación y representación del oferente**. **B pp.15–17; A1** | — | — | PE | Anexo 1, RUT, antecedentes del representante, documentos societarios y poderes vigentes si corresponde. |
| AD-08 | **Oferta técnica, económica y plazo de implementación**. **B pp.17–19; A3** | — | — | PE | Anexo 3, alcance de ambos servicios, precio neto consistente y plazo comprometido. Más de 30 días hábiles es inadmisible según tabla; el plazo no debe inventarse antes de un plan técnico. |
| AD-09 | **Programa de integridad** (criterio de evaluación). **B pp.19–20; A5** | — | — | PE | Anexo 5 y respaldos de conocimiento/implementación; distinguir la pérdida de puntaje de una causal de inadmisibilidad. |
| AD-10 | **Garantías, titularidad y obligaciones comerciales**. **B pp.25–26,31,34; Q12, Q15–Q16, Q22** | — | — | PE | Validar garantía de fiel cumplimiento, prohibición de subcontratación de ejecución, proveedores auxiliares autorizables, continuidad de 12 meses, pagos contra recepción y derechos sobre software preexistente. Revisión contractual externa. |

### 2.2 Reglas electorales y funcionalidades — CLEP

| ID | Requisito y base | F | V | X | Evidencia / criterio objetivo de aceptación pendiente |
|---|---|:--:|:--:|:--:|---|
| CL-01 | Cinco elecciones independientes y simultáneas por estamento; segregación del voto. **B pp.42,44–45, nn.10–11** | P | L | — | E2E de cinco elecciones, padrones/candidaturas/urnas/cómputos separados y rechazo de voto en estamento indebido. |
| CL-02 | Padrón de hasta 20.000, carga Excel/CSV y rechazo de duplicados; informe de calidad dentro de 5 días hábiles. **B p.45, nn.11–12.1; Q32–Q38** | P | L | DI | Ensayo con cinco padrones sintéticos y 20.000 registros; reporte de inconsistencias, aceptación institucional y congelamiento por estamento. El SLEP aporta los padrones consolidados y aprueba su contenido. |
| CL-03 | Sufragio directo, secreto, unipersonal y una preferencia. **B pp.42–43, n.10** | P | L | PE | Votación con Belenios o motor verificado que separe identidad y preferencia, unicidad y prueba independiente de secreto; no utilizar el MVP como prueba de este requisito. |
| CL-04 | Quórum de **30% por cada estamento**; denominador congelado y participación en tiempo real. **B pp.43–45,47,50** | P | ND | — | Pruebas de frontera (29,99% / 30%), cálculo individual por cinco padrones y tablero que no revela preferencia antes de cierre. |
| CL-05 | Nueva elección solo del estamento sin quórum; **sin mínimo de participación**, habilitada en 48 h tras instrucción. **B pp.43–44,50, n.12.9; Q23** | ND | ND | DI | Ensayo completo con padrón/candidaturas heredados, nuevo período, nueva urna, trazabilidad, resultados propios y acta; regla jurídica aprobada por institución. |
| CL-06 | Proclamación de **dos primeras mayorías** por estamento y resultados completos. **B pp.43,50** | ND | ND | — | Casos de prueba con diferentes órdenes y empate en posición de corte; prohibir proclamación automática ante empate. |
| CL-07 | Empate: detectar, **registrar sorteo ante ministro de fe**, sin resolverlo aleatoriamente el servidor. **B pp.43,50** | ND | ND | PE | Flujo controlado con acta, firma y evidencia externa del sorteo efectivamente realizado. |
| CL-08 | Papeleta por estamento: nombre, establecimiento, fotografía, instrucciones, visualización móvil. **B pp.45–46** | P | L | — | Revisión UI con todos los campos y cinco tipos de estamento en navegadores/dispositivos exigidos. |
| CL-09 | Dos mecanismos de identificación **combinables**, incluidos RUN+OTP y alternativas por estudiantes. **B p.47, n.12.4; Q24–Q31** | P | ND | PE | Selección y aprobación institucional de mecanismos por estamento; prueba de envío/expiración/no reutilización del OTP, recuperación, contactos compartidos y suplantación. Validación RUT no equivale a autenticación. |
| CL-10 | Ceremonia de claves: **≥3 custodios** y umbral sin descifrado unilateral; acta/video. **B pp.46–47; Q14** | P | L | PE | Ceremonia con operadores/custodios independientes, ensayo de ausencia de custodio, prueba de descifrado en quorum y evidencia audiovisual, firmada y custodiada. |
| CL-11 | Comprobante de participación sin revelar preferencia. **B p.47** | P | L | — | Prueba de contenido de recibo y posibilidad de verificación sin vincular persona/opción en registro observable. El hash MVP no basta. |
| CL-12 | Congelar padrón, candidaturas y parámetros al abrir; bitácora de intentos de cambio. **B pp.45–46; n.12.1** | P | R | — | Repetir pruebas de inmutabilidad, concurrencia, permisos y bitácora sobre motor final integrado y PostgreSQL del destino. |
| CL-13 | Modalidad híbrida y votación presencial asistida: **consolidación, cuatro ojos y trazabilidad**. **B pp.47–48, nn.12.5–12.6; Q11** | ND | ND | PE | Dos aprobadores distintos para carga presencial; suma consistente sin doble conteo; secreto del voto asistido y aprobación/acta institucional. No confundir con acceso web desde punto asistido. |
| CL-14 | Monitoreo de participación segregado por estamento y reportes sin revelar voto. **B pp.47,53** | P | L | — | Dashboard de cinco elecciones con conteos exactos del motor Belenios verificados; separar participación de resultados cifrados. |
| CL-15 | Actas de apertura/cierre/escrutinio por estamento, sello de tiempo, **firma electrónica** y expediente para proclamación. **B pp.49–50,53** | P | L | PE | PDFs oficiales completos desde resultados verificados Belenios, evidencia firma electrónica y validación del ministro de fe; no reutilizar acta MVP para urna externa. |
| CL-16 | Difusión, manuales, videos accesibles y capacitaciones por perfil. **B pp.48–49, n.12.7; Q39–Q40** | — | ND | PE | Paquete editable, guías por perfil, video subtitulado, sesiones virtuales acordadas, asistencia y aprobaciones institucionales. |

### 2.3 Funcionalidades — mutualidad y requisitos transversales

| ID | Requisito y base | F | V | X | Evidencia / criterio objetivo de aceptación pendiente |
|---|---|:--:|:--:|:--:|---|
| MU-01 | Elección de mutualidad: padrón referencial **4.023**, quórum **60%**, participación sin estamentos salvo instrucción. **B p.56, n.18** | P | ND | — | Ensayo de aceptación con base sintética de 4.023, umbral de 60% y acta de participación. |
| MU-02 | ≥2 mecanismos combinables (correo OTP/SMS/RUN/documento/TOTP u otro); posibilidad de RUN+OTP. **B p.57, n.20.2; Q31** | P | ND | PE | Dos opciones técnicamente operativas, configurables y aprobadas; pruebas de entrega, recuperación, expiración y validación de identidad. |
| MU-03 | Cifrado, secreto, sellado de tiempo, urna inalterable y unicidad. **B p.57, n.20.3** | P | L | PE | Proveedor Belenios real en destino con verificadores externos, autoridades separadas y registros completos auditables. |
| MU-04 | Inicio/cierre automáticos, blancos/nulos configurables y alternativas con logo/orden. **B p.58, nn.20.5–20.6** | P | ND | — | Pruebas de programación horaria, zona de tiempo, blanco/nulo real en el motor escogido, logos y congelamiento. Belenios ADR solo soporta selección obligatoria sin blanco/nulo. |
| MU-05 | Resultados y actas de mutualidad con firma y distribución en Excel/CSV/PDF. **B pp.58–59** | P | L | PE | Casos con votos válidos/blancos/nulos, suma coherente y actas firmadas; exportación verificable de todos los registros acordados. |
| TR-01 | Acceso web responsive, navegadores vigentes y anteriores, sin instalación. **B pp.46,56–57** | P | L | — | Suite cross-browser Chrome, Edge, Firefox y Safari, móviles/tabletas, sin fallos críticos. La UI React existente no acredita cobertura completa. |
| TR-02 | **WCAG 2.1 AA**, teclado y lector de pantalla; declaración en oferta técnica. **B p.46, n.12.2** | P | ND | PE | Auditoría WCAG 2.1 AA de flujos completos; pruebas teclado/lector de pantalla y declaración técnica firmada. |
| TR-03 | Abrir/cerrar y resultados sin contaminación entre motores MVP y Belenios. **B pp.42,50,57–58** | P | R | — | Suite cruzada de ámbito/motor/tenants sin aceptación de voto en urna incorrecta ni resultados falsos a partir de `Vote`. |
| TR-04 | Entregables de ambos servicios, informes, respaldos, videos y eliminación segura. **B pp.52–54,58–59** | P | ND | PE | Lista de control E1–E10 CLEP y E1–E8 mutualidad, con muestras completas en formatos solicitados y recepción institucional simulada. |

### 2.4 Seguridad, continuidad, operación y tratamiento de datos

| ID | Requisito y base | F | V | X | Evidencia / criterio objetivo de aceptación pendiente |
|---|---|:--:|:--:|:--:|---|
| OP-01 | **≥2.000 concurrentes CLEP** y **≥200 mutualidad** sin degradación; **≤3 s** por transacción. **B pp.55,59, nn.16/22** | P | ND | PE | Informe de prueba de carga reproducible, con identificación de entorno/datos, percentiles, errores, simultaneidad y aceptación de servicio. |
| OP-02 | Disponibilidad **≥99,8%** y plataforma 24 h durante toda ventana. **B pp.47,54–55** | P | ND | PE | SLO/monitoreo horario, alertas, prueba failover y reportes íntegros del destino con evidencia real. |
| OP-03 | **RPO ≤5 min; RTO ≤30 min**; respaldo de urna y ensayo de falla 48 h antes. **B p.54, n.15** | P | L | PE | Restauración integral de base, claves, urna Belenios y auditoría en infraestructura destino, midiendo RPO/RTO; la restauración de 13 tablas de laboratorio es insuficiente. |
| OP-04 | Soporte CLEP: primer contacto **≤15 min** telefónico/mensajería, **≤2 h** correo, críticos **≤60 min**, atención 08–22 y guardia 24 h. **B p.55; Q7–Q10** | — | ND | PE | Procedimientos, personal/guardias, simulaciones y tickets fechados; soporte remoto centralizado permitido cuando equivalente. |
| OP-05 | Seguridad: **MFA administrativo obligatorio**, RBAC, revocación en ≤24 h. **B p.61, n.24** | P | ND | PE | Ensayo real del segundo factor para todos los administradores y revocación; cookies, JWT, CSRF y roles no sustituyen MFA. |
| OP-06 | TLS vigente, **cifrado en reposo** y custodia de secretos. **B pp.57,61** | P | L | PE | Evidencia de configuración y auditoría externa del destino (TLS/DB/objetos/backup/rotación), incluidos servidores de urna. |
| OP-07 | WAF, mitigación DDoS, rate limiting y gestión de vulnerabilidades. **B p.61** | P | L | PE | Tests WAF/DDoS, reportes de parches y escaneos/penetración externos; pruebas rate limiter no demuestran WAF/DDoS. |
| OP-08 | Desarrollo/pruebas/producción segregados; no usar PII real en pruebas. **B p.61** | P | L | PE | Inventario de entornos, IAM, datos sintéticos y acta de segregación; evidencias de accesos mínimos. |
| OP-09 | Log completo e inalterable, reconstrucción sin comprometer secreto; copia íntegra al SLEP. **B p.62, n.26** | P | R | PE | Exportación de bitácora y anclajes en custodio independiente, recuperación y verificación tras borrado/restauración; pruebas de cadena interna son parciales. |
| OP-10 | Notificar incidentes de seguridad **≤4 h**; informe de causa raíz en 5 días hábiles; brechas de datos personales **≤24 h**. **B pp.61–62, nn.24–25** | — | ND | PE | Procedimientos diferenciados, responsables, canales y simulacro con trazabilidad de acuses y plazos. |
| OP-11 | Residencia de datos en Chile o autorización **previa y escrita** para excepción. **B pp.61–62; Q13** | P | ND | PE | Mapa de flujos, regiones de procesamiento/almacenamiento/backup, contrato cloud y autorización formal cuando se use otra jurisdicción. Q13 no sustituye automáticamente la autorización escrita del numeral 25. |
| OP-12 | PII solo para finalidad electoral; **prohibido introducir padrón/resultados en IA generativa de terceros** sin permiso. **B p.61, nn.24–25** | P | ND | PE | Inventario de encargados/subencargados, controles anti-exfiltración, cláusulas y evidencia de no transferencia a servicios generativos sin autorización. |
| OP-13 | Derechos de titulares, privacidad, acuerdo de confidencialidad y certificado de **borrado seguro** tras autorización (≤30 días). **B pp.61–62, n.25** | P | L | PE | Procedimiento y prueba de supresión con respaldos/urnas, cadena de custodia, constancia firmada; respetar retención legal/hold y titularidad de datos institucionales. |
| OP-14 | Ceremonia de escrutinio en ≤24 h, video íntegro/acta y entrega del registro dentro de 24 h. **B pp.49–50,55** | P | L | PE | Ensayo integral de desencriptado con custodios independientes, actas, sello de tiempo, archivo audiovisual y acuse institucional. |
| OP-15 | Plataforma activa de **12 meses**, con capacidad para procesos adicionales. **B pp.26–29; Q15–Q16** | — | ND | PE | Contrato con alcance/costos, presupuesto de soporte sostenido, plan de continuidad y fecha de baja; evitar confundir una jornada con toda la obligación contractual. |
| OP-16 | Fuente/secretos/infraestructura controlables, operación sin dependencia no autorizada. **B pp.31,61–62; Q12, Q22** | P | L | PE | Contratos de infraestructura/encargados, SLAs, custodia de claves y auditorías; propiedad del software preexistente no traslada datos del SLEP. |

## 3. Casos de aceptación transversales propuestos

Estas pruebas son **criterios futuros**, no comprobaciones ejecutadas en esta revisión:

1. **AT-01 — Integridad de padrón y estamentos:** cinco padrones sintéticos (hasta 20.000 habilitados), RUT e identificadores alternativos, personas con contactos compartidos, duplicados, separaciones de ámbito y cambios rechazados tras congelar.
2. **AT-02 — Flujo individual y privacidad:** elección abierta, autenticación multifactor, una preferencia, rechazo de doble voto, sufragio secreto y verificación pública del resultado sin correlación identidad–preferencia.
3. **AT-03 — Regla CLEP:** quórum exactamente 30% y bajo 30% por cada estamento, dos primeras mayorías, empate con sorteo documentado y nueva elección sin quórum mínimo solo donde corresponda.
4. **AT-04 — Mutualidad:** 4.023 electores sintéticos, quórum 60%, blancos/nulos configurables en motor final, sello de tiempo, escrutinio y actas verificables.
5. **AT-05 — Autenticación inclusiva:** al menos dos métodos utilizables, RUN+OTP, estudiantes sin correo/teléfono propio, falla de entrega, contactos compartidos, rate limiting y recuperación con autorización institucional.
6. **AT-06 — Criptografía institucional:** tres custodios de organizaciones/personas diferentes, umbral de descifrado, imposibilidad de descifrado unilateral por operador, verificadores y actas externas.
7. **AT-07 — Híbrida/puntos asistidos:** carga manual de resultados autorizada por dos personas distintas, trazabilidad, consolidación y acta, sin mezcla de modalidades ni vulneración del secreto.
8. **AT-08 — Resiliencia y carga:** 2.000/200 sesiones concurrentes, tiempo de respuesta ≤3 s bajo carga, monitoreo y failover con RPO/RTO medidos sobre urna y BD reales del ensayo.
9. **AT-09 — Cierre y transferencia:** firma electrónica, resultados CSV/Excel/PDF, bitácoras completas, ceremonia grabada, aprobación institucional, traslado de propiedad de datos y borrado seguro certificado.
10. **AT-10 — Evaluación independiente:** auditoría de seguridad con alcance, penetración, WCAG 2.1 AA, análisis legal y documentación externa separada de los artefactos CI internos.

Para cada ensayo conservar como mínimo: **ID de caso, fecha, SHA de código e imágenes, manifiesto de infraestructura, entorno, volumen y clase de datos, procedimiento reproducible, resultados esperados/reales, artefactos hash, responsable, revisor independiente cuando se exija, incidentes, resolución y firma de aceptación**. Evidencia privada y datos personales deben custodiarse fuera del repositorio público.

## 4. Compuertas y decisiones

| Compuerta | Condición necesaria | Estado al corte |
|---|---|---|
| **G-R0: referencia registrada** | Bases trazadas a requisitos F/V/X con fuentes/versiones y brechas | Esta matriz puede cumplir G-R0 al revisarse y fusionarse como documentación. |
| **G-R1: aptitud funcional demostrada** | Todas las filas funcionales aplicables en `I`; AT-01–AT-09 aprobadas en entorno representativo y no solo demo | **NO ACREDITADA**. |
| **G-R2: aptitud operacional/de seguridad** | Carga, accesibilidad, MFA, continuidad, custodia/verificación, seguridad externa y datos aprobados | **NO ACREDITADA**. |
| **G-R3: idoneidad para contratar** | AD-01–AD-10 y `X=EX` donde corresponda; revisión administrativa y jurídica con convocatoria vigente | **NO ACREDITADA**. Es independiente del estado del software. |
| **G-R4: elección vinculante** | Además de G-R1/R2 y de la contratación específica, permisos, custodios, reglas institucionales, piloto y aceptación G4 del [ADR/Sprint 3](../Sprint_3/matriz-aceptacion.md) | **NO AUTORIZADA**. |

**Regla de gobernanza:** un cambio a esta matriz **no modifica automáticamente** las puertas M1/M2/G3/G4, las configuraciones `BELENIOS_MODE`, bases de datos, infraestructura, credenciales ni el estatus contractual. No utilizar `EX` sin cargar una referencia inequívoca a evidencia externa válida. No computar porcentaje global de avance sumando requisitos jurídicos y técnicos heterogéneos.

### Riesgos/decisiones de la licitación de origen que NO deben generalizarse

- **Cronograma contradictorio:** Q3 fija CLEP el 25-11-2026 y mutualidad a más tardar 30-11-2026; el calendario de adjudicación y las condiciones de tramitación/ajuste de B p.52 deben verificarse por separado. No derivar un plazo de desarrollo de esta convocatoria.
- **Soporte presencial vs remoto:** B pp.47,60 contempla monitores; las respuestas aceptan modelo remoto equivalente. Registrar el modo efectivamente autorizado **por proceso**, no marcar el requisito como eliminado.
- **Certificado externo de seguridad:** Q1 admite certificación de empresa externa, pero alcance, independencia y evidencia sustantiva siguen siendo necesarios; una prueba de penetración aislada no se autodeclara equivalente.
- **Infraestructura de terceros y localización:** Q12–Q13 flexibilizan uso de servicios auxiliares y almacenamiento; B n.25 exige residencia chilena o excepción previa escrita. Ante tensión textual, solicitar definición jurídica/institucional para la convocatoria concreta.
- **Terceros y UTP:** no asumir que una alianza permite transferir automáticamente experiencia ni sortear prohibiciones de subcontratación; verificar elegibilidad, ejecución y titularidad según bases de la oportunidad respectiva.
- **Aplicación temporal:** la convocatoria ID 1375746-20-LE26 es **únicamente un caso de referencia de 2026**. Esta matriz seguirá siendo un backlog de aspiración hasta ser contrastada con cualquier nueva licitación y sus reglas vigentes.

## 5. Mantenimiento

- **Propietario funcional:** responsable de producto electoral. **Responsable técnico:** ingeniería y operador de infraestructura. **Responsable de aceptación externa:** institución/autoridad, auditor tercero, jurídico o mandante, según fila.
- Cada cambio de `F/V/X` requiere fecha, actor, SHA exacto, referencia a prueba o documento y alcance. Para `EX` registrar emisor, fecha de vigencia, objeto/cobertura, repositorio de custodia y verificación independiente; nunca publicar documentos privados.
- Antes de un piloto o propuesta pública, levantar una **matriz de brechas actualizada** sobre la rama desplegable y convertir los casos AT en pruebas automatizadas y ensayos operacionales controlados, sin degradar controles previos.
- Se permite cerrar tareas de documentación de referencia sin habilitar `BELENIOS_MODE=pilot`, ejecutar elecciones ni anunciar cumplimiento de las bases.