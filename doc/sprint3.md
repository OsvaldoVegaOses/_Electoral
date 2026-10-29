# Sprint 3 — Cierre de Sprint 2, integración a main y activación controlada de Belenios

**Proyecto:** TheoGen Electoral.

**Fecha:** 2026-10-28, Chile.

**Estado:** EN IMPLEMENTACIÓN LOCAL desde 2026-10-29; [avance y evidencia](Sprint_3/estado-implementacion.md). M1 y M2 pendientes de aceptación.

**Origen:** solicitud del titular de preparar el Sprint 3 para cerrar los pendientes y determinar los requisitos de funcionamiento con Belenios activo.

**Diagnóstico complementario:** [Requisitos de activación Belenios](Sprint_3/activacion-belenios.md).

## 1. Objetivo y resultados de salida

Consolidar Sprint 2 y la integración ADR-001 en una versión reproducible, corregir los contratos pendientes y preparar la aplicación para una elección piloto completa con Belenios. La preparación original fue documental; la solicitud de continuación habilita la implementación local. La activación conserva sus gates.

Se establecen dos entregas con aceptación independiente:

| Entrega | Resultado exigido | Condición para declararla terminada |
|---|---|---|
| **M1 — Integración y cierre de Sprint 2** | Candidato único con Sprint 1, S2-A/B/C/D/E, PoC y ADR reconciliados; PR final contra `main` | Criterios originales de Sprint 2 satisfechos, CI del SHA final, evidencia y revisión independiente. La fusión es una acción posterior sobre el candidato revisado; Belenios puede permanecer apagado. |
| **M2 — Belenios activo para piloto no vinculante** | Aplicación y urna operables por usuarios de prueba, con identidad, entrega, autoridades, resultados y recuperación reales | M1 aceptado, configuración de destino verificada, requisitos institucionales G2 aplicables y autorización G3. Primero ensayo sintético; participantes reales solo dentro del alcance expresamente aprobado. |

Si una dependencia externa impide M2, emitir su estado BLOQUEADO/PENDIENTE y entregar lo efectivamente probado. M1 no se declara completo si faltan sus propios criterios. Una reducción del alcance de Sprint 2 requiere aceptación escrita y se informa como tal; no equivale a cumplir íntegramente el mandato original.

La elección vinculante corresponde a G4 del ADR y tiene aceptación propia. Ni M1, ni M2, ni fusionar código autorizan por sí solos ese uso.

## 2. Línea base verificada y límites

Las referencias de esta tabla son un corte de la revisión, no valores que deban imponerse a una rama que haya avanzado.

| Elemento | Estado observado | Implicación |
|---|---|---|
| `main` en GitHub | `0b654e5883145d629f331807693a1db7c9b67134` | Continúa en el commit inicial. |
| Rama ADR | `feat/adr001-belenios-integration`, `d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9` | 29 commits y 153 archivos respecto de `main`; contiene Sprint 1, S2-A/B y H0–H4, además de la implementación ADR. |
| PR ADR | [PR #9](https://github.com/OsvaldoVegaOses/_Electoral/pull/9), abierto y en borrador contra `integration/adr001-base` | Todavía no es el PR final de integración a `main`. La revisión anterior comprobó nueve PR abiertos en borrador. |
| Árbol principal S2 | `fix/s2-c-pii-privacy-tokens`, HEAD `65c164c7bb4073d5250c04d8f8cb40095a759ffb` | Antes de añadir estos documentos: 67 rutas modificadas/nuevas, incluidos resultados generados. No son 67 cambios aptos para publicación automática. |
| Candidato selectivo | `fix/s2-cde-selected-close`, mismo HEAD | La revisión comprobó 45 rutas con cambios y 18 archivos compartidos con contenido diferente al árbol principal. Hay que reconciliar los candidatos. |
| Backend S2 local | Reporte `.runtime/s2-integration.json`: 165 casos, 0 fallos, 0 omitidos; PostgreSQL 16/Redis 7 y restauración exacta de las tablas comprobadas | Evidencia preexistente inspeccionada, no suite repetida al redactar este sprint. JUnit SHA-256: `ce9c65ac8e33ce361b6e6a6674f359a3ecb9eb157c287e6ec018c133dd4d1c89`. No contiene una aprobación del futuro árbol integrado. |
| Evidencia ADR | Informe versionado: 127 pruebas backend aprobadas/8 omitidas, cuatro casos PostgreSQL aparte, cinco contratos UI; recorrido real agregado 1/1 | Pruebas de ramas y entornos distintos; no sumar los recuentos como si fueran una ejecución final. |
| CI remota | [Run 40765712777](https://github.com/OsvaldoVegaOses/_Electoral/actions/runs/40765712777) del SHA ADR, fallido antes de ejecutar pasos | La anotación de GitHub indica bloqueo de cuenta por facturación. Requiere intervención del administrador de la cuenta. |
| Activación | Cliente y UI limitados a `laboratory` + `development`, destinos loopback y runtime Docker del PoC | Existe integración controlada; falta un contrato de despliegue y operación fuera del laboratorio. |

Los informes anteriores que dicen que Docker no estaba disponible o que PostgreSQL/Redis nunca se ejecutaron deben conservarse como historia y recibir una actualización fechada. La evidencia local nueva tampoco acredita CI, custodia independiente, entrega externa ni despliegue.

## 3. Reglas de ejecución

1. Inventariar primero HEAD, ramas, worktrees, cambios y evidencias; conservar los árboles originales y su trabajo ajeno. Preparar una rama aislada desde la integración publicada más reciente, verificando si `d9a6def` sigue siendo la base adecuada.
2. Seleccionar por archivo y por hunk. No publicar `.runtime/`, correo, claves, correspondencias privadas, bases, dumps ni resultados brutos de Playwright. Publicar solo evidencia sanitizada y sus hashes.
3. Mantener intención persistida, exclusión transaccional, `If-Match`, control de propietario y bloqueo ante resultado remoto `UNKNOWN`. No repetir ni reparar automáticamente una mutación incierta.
4. No trasladar votos históricos de `Vote` a Belenios ni borrar columnas para afirmar secreto. Las elecciones históricas mantienen procedencia y restricciones; las nuevas vinculadas no pueden volver al motor MVP como fallback.
   Conservar la criptografía y semántica del protocolo upstream; ampliar papeletas solo mediante modalidades soportadas y verificadas. No construir un motor criptográfico propio ni parchear el protocolo para simular blanco/nulo.
5. Usar datos sintéticos y recursos de prueba identificados. Pruebas destructivas de migración/restore solo en bases propias desechables. Las migraciones sobre datos operacionales y la retención destructiva tienen procedimientos y autorización específicos.
6. No hacer pasar desarrollo por producción cambiando `ENVIRONMENT`. La activación se implementa como capacidad explícita, con configuración y pruebas del entorno de destino.
7. La preparación local y los PR revisables no sustituyen la aceptación final para fusión, despliegue, gastos o uso de participantes reales. Registrar las autorizaciones ya existentes y pedir solo las que falten al llegar a la acción concreta.

## 4. Backlog y dependencias

Responsables son funciones propuestas; se deben asignar personas al iniciar. Ninguna fila se considera ejecutada por estar incluida en este documento.

| ID | Prioridad | Entregable | Responsable | Dependencias |
|---|---|---|---|---|
| S3-00 | P0 | Inventario, alcance y candidato único | Ingeniería + titular | Ninguna |
| S3-01 | P0 | Migraciones y actualización/recuperación coherentes | Backend + datos | S3-00 |
| S3-02 | P1 | CI bloqueante y reproducible | Ingeniería + administrador GitHub | S3-00; desbloqueo de cuenta para ejecución remota |
| S3-03 | P0 | Privacidad, padrón y credenciales separadas por motor | Backend + producto + autoridad de credenciales | S3-00/01; decisión S2-07 y canal |
| S3-04 | P1 | Auditoría concurrente y custodia verificable | Backend + auditor/custodio | S3-01; custodio designado |
| S3-05 | P0 para M2 | Adaptador, verificador y despliegue fuera del PoC | Backend + operación | Diseño de destino; S3-00/01 |
| S3-06 | P0 para M2 | Autenticación electoral y ceremonia independiente | Operación + identidad + custodios | S3-03/05; decisiones G2 |
| S3-07 | P1 | Aplicación completa: panel, resultados, dashboard y actas | Frontend + backend + producto | S3-03/05; reglas de papeleta |
| S3-08 | P0 | E2E, seguridad y recuperación del candidato final | Ingeniería + operación + revisor | Implementaciones anteriores; repetir controles afectados |
| S3-09 | P0 | Informe M1, revisión y PR final a `main` | Ingeniería + revisor independiente + titular | Criterios M1 de S3-00…08 |
| S3-10 | P0 para M2 | Ensayo, aceptación y activación de piloto G3 | Comisión + operación + titular | M1; S3-05…08; aprobación G3 |

### S3-00 — Consolidación y resolución de alcance

- Registrar un manifiesto con rutas incluidas/excluidas, hashes, base y procedencia. El árbol principal tiene avances de S2-07 y Brevo que no están en el candidato selectivo; no copiar uno entero sobre el otro.
- Comparar los cambios S2 con ADR en permisos, CSRF, modelos, rutas de voto/informes, configuración, workflow e interfaz. Los solapamientos de archivos no equivalen por sí solos a conflictos de merge.
- Proponer resolver S2-07 con el paquete HMAC completo y coordinado, dado que el objetivo nuevo es cerrar pendientes. Registrar la decisión antes de su implementación/publicación: el diferimiento anterior no queda revocado por redactar un sprint. Si continúa diferido, conservar el hallazgo abierto y explicitar la aceptación de un alcance reducido.
- Reconciliar el estado del ADR: la rama de integración registra G1 e implementación controlada autorizados; el mandato histórico de Sprint 2 aún dice PROPUESTO. Conservar el historial y publicar un estado vigente único, sin atribuir aprobación institucional o G3/G4 inexistentes.

**Salida:** candidato revisable, trazabilidad de todos los pendientes y decisión de alcance registrada.

### S3-01 — Esquema, datos legacy y recuperación

- Reconciliar las cabezas `c3d4e5f6a7b8` y `bel001_20261028`, incluyendo la dependencia HMAC si forma parte del candidato. No basta reunir archivos y ejecutar `upgrade head`.
- Revisar cambios a revisiones publicadas `e5f6a7b8c9d0` y `f6a7b8c9d0e1`; definir cómo reciben la corrección bases que ya las aplicaron. No suponer que editar el archivo repite una revisión aplicada.
- Probar instalación vacía y actualización desde Sprint 1, S2-B aplicado y base ADR, con datos sintéticos Borrador/Abierta/Cerrada/Finalizada. Comparar votos, derechos consumidos, denominadores, representantes, operaciones y hashes.
- Mantener rechazo de auditoría legacy sin hash hasta existir inventario, backup y reconciliación ensayada. Diferenciar downgrade de esquema y restauración protegida cuando el backfill no sea reversible.
- Separar rol migrador y rol de aplicación; ejecutar DDL como una operación de release coordinada, evitando carreras entre réplicas al arrancar.

**Salida:** un head soportado, matriz de rutas de actualización y restore probado sin pérdida de votos reconocidos ni duplicación de derechos.

### S3-02 — CI y controles requeridos

- El administrador resuelve el bloqueo de facturación de GitHub y confirma disponibilidad de runners. Ingeniería prepara el workflow mientras se resuelve; no cambiar facturación ni contratar servicios por este mandato documental.
- Instalar dependencias desde pins/lockfiles en entorno limpio. Si difieren de los entornos locales previos, probar las versiones declaradas y corregir incompatibilidades y hallazgos de seguridad.
- Configurar bases separadas para suite principal, concurrencia, migraciones vacías, backfill y privacidad. Conservar `REQUIRE_S2_SERVICES=1` y las URLs explícitas en el candidato elegido; ningún gate obligatorio aprueba por skip.
- Reunir backend/migraciones PostgreSQL 16, Redis 7, lint/build, E2E MVP y Belenios, escáneres, Compose/Nginx/TLS y recuperación. Retirar `continue-on-error` de Gitleaks en el workflow ADR; resolver excepciones puntuales de forma revisable.
- Ejecutar Nginx con resolución válida de upstream; generar JUnit/HTML y cargar evidencia sanitizada también ante fallo. Revisar trazas antes de su retención: pueden contener credenciales aunque el código no las imprima.
- Comprobar permisos para configurar reglas de rama; exigir los checks adecuados y revisión independiente sin dejar una vía normal de bypass.

**Salida:** URL de ejecución verde del SHA candidato exacto, checks requeridos, dependencias identificadas y artefactos recuperables.

### S3-03 — Privacidad, padrón y dos contratos de credenciales

- Completar PII masiva, retención por fecha de cierre, legal hold, idempotencia y denominadores congelados. Incluir datos/respaldos/representantes Belenios en el inventario de retención; no alterar pruebas públicas para simular anonimato.
- Si se incorpora HMAC, reunir lector, provisión, normalización, migración, configuración y pruebas. Exigir clave persistente independiente, recuperación real controlada y fallo seguro con clave ausente/incorrecta; no crear otro derecho para compensar un fallo de clave.
- Separar el alta/importación de padrón de la emisión de tokens MVP. Actualmente esas rutas llaman `require_credential_delivery()`, que bloquea producción; debe poder prepararse el padrón de una elección Belenios sin emitir credenciales MVP ni quitar globalmente el guard.
- Para el motor MVP que siga soportado, completar provisión, entrega, reemisión, estados persistidos y conciliación. El transporte Brevo existente no implementa ese ciclo. No persistir tokens en claro ni desactivar la credencial anterior silenciosamente ante envío incierto.
- Para Belenios, las credenciales privadas y claves de trustees se generan/custodian fuera de TheoGen. La aplicación conserva solo las referencias mínimas de entrega y correspondencia autorizada; no reutiliza `token_hash` ni el JWT como credencial Belenios.

**Salida:** pruebas de PII/derechos y contratos de entrega diferenciados. Eliminar el soporte activo de emisión MVP, si se propone, requiere una decisión de producto y de alcance; no cierra automáticamente S2-05 original.

### S3-04 — Auditoría y custodia

- Probar 100 eventos simultáneos con sesiones PostgreSQL independientes y al menos dos procesos; verificar orden, head, rollback y atomicidad con el negocio. Confirmar que el rol de aplicación no puede editar ni borrar registros.
- Registrar eventos de gestión Belenios sin credenciales, selecciones o correspondencias innecesarias. La tabla de intenciones remotas no reemplaza una bitácora protegida.
- Exportar checkpoint con secuencia, conteo, head, fecha y digest; obtener recibo de un custodio fuera del control de la aplicación y hacer que otra persona lo recupere/verifique.
- Ensayar alteración, borrado de prefijo/medio y truncamiento contra el checkpoint, también tras restore. Mantener la purga física bloqueada si no hay un diseño de épocas verificable.
- Distinguir dos anclajes: bitácora TheoGen y archivo/resultado electoral Belenios. Una evidencia no sustituye la otra.

**Salida:** cadena y checkpoints verificables, evidencia de custodia y límites ante administradores privilegiados. Si se acepta una operación bloqueada como mitigación conforme al DoD de Sprint 2, registrar esa decisión; M2 exige su propio plan de monitor y custodia electoral.

### S3-05 — Adaptador y arquitectura operativa

- Sustituir las dependencias de loopback, nombres de contenedores y redes del PoC por configuración administrada. Usar destinos fijos permitidos, TLS verificado y credenciales con acceso mínimo; no aceptar URLs arbitrarias desde el navegador.
- Separar URL pública de votación/administración y URL de control entre servicios. Dentro de un contenedor `127.0.0.1` no identifica otra urna.
- Diseñar un verificador aislado fuera del API web: recolecta datos públicos y ejecuta la herramienta compatible sin red sobre montaje de solo lectura. El API no recibe socket Docker, claves privadas ni capacidad general de ejecutar comandos.
- Reemplazar `docker inspect/exec` del runtime de laboratorio por una evidencia operativa controlada de versión y política R1/R2. En la referencia 3.3.0 el flag R2 es de instancia: aislar políticas o soportar solo la aprobada.
- Crear configuración de activación por entorno/institución; apagar mutaciones conserva vínculos, resultados y bloqueo del motor MVP. No habilitar el entorno mediante `development` en un servidor real.
- Preparar manifiestos de despliegue con PostgreSQL, Redis, persistencia Belenios, secretos, proxy TLS, healthchecks, logs y backup. La plantilla productiva actual no los reúne.

**Salida:** despliegue reproducible de prueba fuera de las redes del PoC, autenticado y probado en la misma topología prevista para el piloto.

### S3-06 — Identidad, entrega y autoridades electorales

- Elegir y ejecutar autenticación real compatible con 3.3.0 y con los alias. El borrador actual usa autenticación por correo y direcciones `@ejemplo.test`; se debe resolver su entrega o cambiar el contrato de identidad con pruebas.
- Decidir correo con alias/relay o proveedor de identidad compatible; documentar confianza y acceso a correspondencias. OIDC es una opción, no un requisito automático; el JWT de TheoGen no se acepta por sí solo en Belenios.
- Designar autoridad de credenciales externa y tres custodios con umbral 2/3 como propuesta inicial, pendiente de aprobación. Personas/procesos en el mismo host no prueban independencia administrativa.
- Ensayar ceremonia, respaldo de cada custodia, pérdida de una, intento con umbral insuficiente, recuperación y verificación externa. No añadir una nueva identidad electoral al recuperar una credencial ni alterar el padrón validado sin el procedimiento aprobado.
- Validar entrega a destinatarios sintéticos controlados antes de incorporar participantes reales. Si se utiliza un canal de correo, comprobar autenticación del dominio, entrega, rebotes y confidencialidad del material enviado.

**Salida:** una persona autorizada por unidad puede autenticarse y votar; el representante alternativo y el no habilitado son rechazados; las privadas no pasan por TheoGen.

### S3-07 — Aplicación operable con Belenios

- Resolver el dashboard que devuelve 409 al incluir elecciones vinculadas: presentar agregados por motor/fase con procedencia y disponibilidad, sin interpretar ausencia de resultado como cero.
- Habilitar alta/importación y selección de representantes con validación de familia, impugnaciones, congelamiento y trazabilidad. Hacer explícitos motor, estado remoto confirmado y política R1/R2.
- Mantener el sufragio en la interfaz nativa Belenios y proporcionar el enlace público correcto. Completar español y recorrido móvil/accesible de acceso, errores y recuperación.
- Generar actas/PDF y expediente desde resultados verificados Belenios. Mantener bloqueadas las actas basadas en `Vote` para esas elecciones; incluir denominador de unidades, huellas, incidencias y firmas según el modelo aprobado.
- Definir papeleta: el adaptador actual admite una pregunta, una opción obligatoria y no modela blanco/nulo. Si la institución requiere otra modalidad, implementar y verificar el contrato completo antes de aceptarla; `null` no significa cero votos.
- Resolver el límite actual de 100 representantes por preparación frente al volumen previsto: aprobar un piloto dentro del límite o ampliar el contrato y probar carga/tamaño/timeout sin dividir una unidad ni crear urnas duplicadas.
- Definir apertura/cierre manual o programado, zona horaria e incidentes. Si se programa, comprobar quién controla las fechas y cómo se confirma el estado remoto; no afirmar que TheoGen impide votar fuera de plazo si Belenios sigue abierto.
- Resolver operaciones `UNKNOWN` con pantalla de cotejo, rol autorizado y evidencia; no ofrecer reintento ciego ni recreación. Mantener disponibles datos de lectura y soporte cuando un proveedor cae.

**Salida:** administrador, comisión, representante y auditor completan sus recorridos sin depender de comandos privados del desarrollador ni de endpoints MVP incompatibles.

### S3-08 — Verificación final y operación

Ejecutar la matriz de la sección 6 sobre el árbol integrado y después de la última corrección relevante. Conservar el SHA, dependencias, entorno, comandos, recuentos, evidencia y límites por ejecución. Las pruebas del PoC que ya aceptaron votos no se repiten sobre sus mismas urnas; crear elecciones sintéticas nuevas cuando el caso lo requiera.

**Salida:** controles M1 verdes; para M2, ensayo completo en el destino previsto, carga acordada, fallos y restore coordinado de aplicación/urna sin perder boletas reconocidas ni duplicar operaciones.

### S3-09 y S3-10 — Cierre, main y piloto

- Emitir informe de Sprint 3 y actualización fechada del cierre Sprint 2. Preparar PR final contra `main` desde el candidato probado y revisar los PR encadenados para no duplicar ni revertir documentos históricos.
- Conservar en el PR la decisión de activación: código integrado y motor apagado, o piloto habilitable solo para instituciones autorizadas. Resolver observaciones de seguridad/producto y aprobación humana independiente antes de la fusión final.
- Antes de M2, realizar ensayo con comisión, autoridad, custodios y auditor; comprobar accesos, entrega, papeleta, votos, cierre, escrutinio, acta, soporte y recuperación. Registrar G2 institucional y G3 con responsables, alcance y fecha.
- La activación concreta se realiza sobre una versión y entorno revisados, con plan de incidentes y aceptación final. Un fallo de verificación, divergencia o estado remoto desconocido bloquea el avance afectado.

## 5. Trazabilidad de los pendientes de Sprint 2

| Hallazgo | Trabajo Sprint 3 | Evidencia mínima de cierre |
|---|---|---|
| S2-01 — PII/UNIQUE | S3-03/08 | 100 electores sin colisión, idempotencia e índices de padrón activo intactos |
| S2-02 — Denominador familiar | S3-01/03/07/08 | 5 personas, 2 familias y 1 voto: 50% antes/después de PII y migración |
| S2-03 — Identidad/selección en MVP | S3-00/05/07 | Riesgo histórico residual explícito; nuevas elecciones Belenios sin boletas en `Vote`; no declarar resuelto el histórico |
| S2-04 — Ámbito comisión | S3-00/08 | 403 en toda API/UI fuera de ámbito, incluida Belenios |
| S2-05 — Tokens/entrega | S3-03/06/08 | Contrato de emisión seguro, entrega controlada, reemisión/conciliación y ausencia de texto claro persistido |
| S2-06 — Congelamiento | S3-01/07/08 | Instantánea reproducible, 409 tras congelamiento, horarios/representantes coherentes |
| S2-07 — `unit_key` | S3-00/01/03/08 | Paquete completo y recuperación de clave probados, o hallazgo abierto bajo reducción de alcance aceptada |
| S2-08 — Retención/hold | S3-03/08 | Antigüedad desde cierre verificable, manual/automático equivalentes y hold respetado |
| S2-09 — Auditoría concurrente | S3-04/08 | Cadena única con procesos/sesiones PostgreSQL, rollback y rol sin privilegios de propietario |
| S2-10 — Custodia externa | S3-04/06/08 | Recibo y verificación independiente; límites/operaciones bloqueadas identificados |
| S2-11 — CI/E2E/escáneres | S3-02/08/09 | Jobs requeridos verdes y evidencia del SHA final |
| S2-12 — Redis/cookies/CSRF | S3-02/05/08 | Dos procesos, caída/expiración y precedencia cookie/Bearer sin bypass |
| S2-13 — Documentación | S3-00/09 | Matriz actual, manuales, riesgos, ADR y PR coherentes con el código y la evidencia |

## 6. Matriz mínima de aceptación

| Caso | Escenario | Resultado obligatorio |
|---|---|---|
| INT-01 | Instalación vacía y cada ruta soportada de actualización poblada | Un head; datos e invariantes conservados; recuperación ensayada |
| PRIV-01 | 100 electores, retención, hold y ejecución repetida | Sin colisión, cambio prematuro ni pérdida de denominadores |
| PRIV-02 | Clave HMAC ausente, incorrecta y recuperada, si se incluye | Bloqueo seguro, mismo derecho recuperado, sin doble voto |
| AUTH-01 | Dos colegios, comisiones sin asignación/cross-tenant, cookie y Bearer | Aislamiento y CSRF coherentes por HTTP real |
| AUTH-02 | Dos procesos, Redis concurrente/expirado/caído al inicio y durante uso | Contadores compartidos; ausencia de degradación silenciosa en producción |
| AUD-01 | 100 eventos, rollback, intento de UPDATE/DELETE con rol normal | Cadena/head válidos y escritura restringida |
| AUD-02 | Alteración/truncamiento y restore frente a checkpoint custodiado | Divergencia detectada y verificación independiente reproducible |
| CRED-01 | Alta/importación, entrega, rechazo, duplicado, timeout y reemisión MVP | Estados persistidos, conciliación y ausencia de exposición; ninguna revocación silenciosa |
| BEL-01 | Preparación Belenios desde padrón sin tokens MVP y entrega/auth reales | Una unidad/representante y ninguna privada dentro de TheoGen |
| BEL-02 | R1 o R2 aprobada; segundo representante, doble submit y pérdida de respuesta | Política ejecutada sin recreación ni reintento de `UNKNOWN` |
| BEL-03 | Ceremonia 2/3, una custodia insuficiente y pérdida de una | Umbral respetado; recuperación y separación demostradas |
| BEL-04 | Cierre, archivo final, prefijo antiguo y resultado alterado | Solo el archivo/resultado completo coincidente con anclaje es publicable |
| APP-01 | Login, creación, padrón, apertura, voto familiar, cierre y PDF | E2E completo con PostgreSQL y proveedor real; roles y totales correctos |
| APP-02 | Dashboard mixto, proveedor caído y función apagada | Estados/procedencia correctos; sin ceros falsos ni fallback MVP |
| OPS-01 | HTTPS, proxy, DNS de servicios, puertos, secretos, logs y health | Configuración del destino validada; sin datos sensibles en capturas/artefactos |
| OPS-02 | Backup/restore de PostgreSQL y persistencia Belenios tras votos aceptados | Mismas boletas/cabeza, mapping y operaciones; sin pérdida ni duplicación; no reanudar un estado anterior sin conciliación |
| OPS-03 | Carga y caída según volumen/ventana acordados | Latencia, error, disponibilidad, RPO/RTO medidos contra objetivos aprobados |
| CI-01 | Workflow sobre último SHA | Cero skips obligatorios; escáneres y jobs requeridos aprobados; reportes conservados |

Los tests con API simulada verifican contratos de UI. No sustituyen el E2E con autenticación real, PostgreSQL y Belenios. El correo aceptado por un proveedor no prueba recepción; un verificador en el mismo host no demuestra independencia administrativa.

## 7. Decisiones y dependencias externas

| Decisión/insumo | Propuesta o trabajo previo | Responsable de resolver | Estado inicial |
|---|---|---|---|
| Alcance S2-07 | Incluir corrección completa; preservar trabajo diferido hasta decisión | Titular + ingeniería | PENDIENTE |
| Soporte MVP | Preservar históricos; definir si nuevas elecciones MVP siguen habilitadas | Producto + titular | PENDIENTE |
| GitHub Actions | Resolver bloqueo de facturación y revisar reglas de rama | Administrador de cuenta/repositorio | BLOQUEADO |
| Destino del piloto | Dominio/DNS/TLS, hosts/servicios, redes y persistencia; verificar recursos existentes antes de comprar | Operación + titular | NO INVENTARIADO |
| Identidad y entrega | Método compatible con alias, canal, remitente y recuperación | Producto + operación + identidad | PENDIENTE |
| G2 institucional | R1/R2, unidad y representante, papeleta, calendario, quórum/desempate | Institución/comisión + titular | PARCIAL según ADR |
| Autoridad/custodios/auditor | Personas y dominios administrativos separados; propuesta umbral 2/3 | Titular + institución | PENDIENTE |
| Retención/legacy/actas/licencias | Políticas, legal hold, respaldo, firmas y revisión jurídica/AGPL | Responsable de datos + asesoría + titular | PENDIENTE |
| Capacidad/continuidad | Electores/unidades, elecciones concurrentes, ventana de voto, SLO y RPO/RTO | Producto + operación | PENDIENTE; no inventar tamaño ni costes |
| Fusión/despliegue/piloto | Aprobar el candidato y el entorno concretos al llegar al gate | Titular + revisor independiente | PENDIENTE |

## 8. Evidencia y definición de terminado

Entregables durante la ejecución: manifiesto del candidato, matriz S2/S3, informe de migraciones/recuperación, pruebas y artefactos sanitizados, diseño de activación, manual de operación, matriz de decisiones y PR final. El informe futuro se propone en `doc/remediacion/08-informe-sprint3-cierre.md`; aún no existe ni se considera evidencia.

Cada evidencia debe registrar: ID de caso, SHA y estado del árbol, versiones/pins/imágenes, entorno y datos sintéticos, comando, resultado, fecha, hash/URL del artefacto, responsable y límite. Si se prueba un árbol sin commit, registrar también su manifiesto de contenido; no atribuir sus resultados automáticamente a un commit posterior.

**M1 terminado:** candidato único, hallazgos originales cerrados o alcance reducido expresamente aceptado, migraciones/datos seguros, CI verde del SHA final, informe actualizado y revisión humana independiente. PR final revisable contra `main`; después de fusionar, comprobar el resultado y checks de `main` antes de dar la integración por terminada.

**M2 terminado:** versión integrada y despliegue aprobado, flujos reales completos, responsables operativos y G2/G3 aceptados, entrega/auth, autoridades, verificación externa, observabilidad y recuperación probadas en el destino. No hay hallazgos bloqueantes abiertos para ese piloto.

**G4 pendiente:** aun con M2 aprobado, la primera elección vinculante requiere aceptación institucional/jurídica y de seguridad específica, simulacro e informe de auditoría. No emitir certificaciones de secreto o legalidad a partir de este sprint.

## 9. Orden de trabajo sugerido

1. S3-00 y decisiones de alcance; iniciar gestiones externas de CI, dominio, canal, custodios y reglas.
2. S3-01/02/03/04; consolidar correcciones y evidencia M1. El diseño de activación puede avanzar con independencia del bloqueo de facturación.
3. S3-05/06/07 y controles afectados de S3-08; implementar con datos sintéticos antes de cualquier participante real.
4. S3-09: revisión del candidato final y PR a `main`, con Belenios apagado mientras falten gates de activación.
5. S3-10: ensayo y activación del piloto solo tras aceptación de su entorno y G3.

No se fija duración, coste ni capacidad de equipo sin conocer las personas y servicios disponibles. Si M2 no cabe en la capacidad acordada, conservarlo como entrega pendiente con sus IDs y criterios; no cerrar sus tareas por haber completado M1.

## 10. Fuentes de la preparación

- [Mandato Sprint 2](sprint2.md), [plan de cierre](Sprint_2/plan-cierre-sprint2.md) e [informe histórico S2](remediacion/07-informe-sprint2-cierre.md).
- [Implementación ADR en el SHA revisado](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/motor/implementacion_adr001.md) y [ADR vigente en esa rama](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/adr/001-motor-de-votacion.md).
- [Requisitos de activación y referencias técnicas](Sprint_3/activacion-belenios.md), derivados de código y evidencias inspeccionados, con los estados de verificación diferenciados.

**Estado de la preparación original:** sprint preparado, sin implementación por esa entrega. **Actualización 2026-10-29:** implementación local en curso; consultar el [informe vigente](Sprint_3/estado-implementacion.md). M1/M2 siguen pendientes; no hubo publicación, fusión o activación en esta continuación.
