# SPIKE-BEL-01 — Mandato técnico para PoC aislada de Belenios 3.3.0 autohospedado

**Proyecto:** TheoGen Electoral
**Estado:** propuesta documental / NO ejecutado
**Fecha:** 2026-10-27
**Base TheoGen:** rama \`fix/pr4-migrations-audit-operations\`, HEAD verificado al redactar: \`1f27936992cd65e001bcf61e1234af25f2c15e78\`
**Motor externo:** Belenios **3.3.0**, etiqueta anotada que apunta al commit \`337887bd1862c7cd057080b530fd80941bfc3c69\`, repositorio espejo https://github.com/glondu/belenios (upstream señalado por el espejo: https://gitlab.com/vcast.vote/belenios).
**ADR:** \`doc/adr/001-motor-de-votacion.md\` **PROPUESTO**. El Gate G1 requiere autorización expresa para ejecutar la PoC. Este documento no concede esa aprobación por sí mismo.
**Relación Sprint 2:** investigación y PoC técnica aislada pueden avanzar en una vía paralela; NO integrar a backend/frontend TheoGen hasta superar los gates y cerrar controles pertinentes del Sprint 2.

## 1. Objetivo y definición estricta de alcance

Demostrar **con evidencia reproducible** si Belenios 3.3.0, autohospedado, puede recibir una elección ficticia, emitir votos cifrados, permitir/denegar revotos según configuración, aceptar credenciales operadas por terceros, usar trustees externos, escrutar y ser auditado por otra persona/máquina, y si su API permite un adaptador de integración futuro con TheoGen.

La PoC **no pretende** certificar protección frente a coacción, garantizar por sí sola el anonimato, hacer elecciones oficiales, probar funcionamiento legal en Chile, realizar despliegues ni automatizar importaciones de RUT reales. Separar evidencias de operación, seguridad y reglas de producto.

**No hacer en esta etapa:** modificar \`Vote\`, \`Voter\`, \`VotingEntitlement\` o rutas de voto existentes; copiar votos históricos; conectar padrones reales; crear integración OAuth productiva; enviar correos reales; exponer servidor demo a Internet; insertar claves privadas/semillas/token API en git; personalizar criptografía de Belenios; forkear/alterar upstream como atajo.

## 2. Hallazgo documental nuevo e importante: revoto

La configuración **exacta de Belenios 3.3.0** contiene el elemento \`<deny-revote/>\` comentado en \`demo/ocsigenserver.conf.in\`, alrededor de las líneas 110–115. El código de esa etiqueta:
- \`src/web/server/common/web_main.ml\` acepta la directiva y establece \`Web_config.deny_revote := true\`.
- \`src/web/server/common/web_persist.ml\` comprueba \`deny_revote\` y devuelve \`RevoteNotAllowed\` en un intento de revoto.

**Por tanto existe una capacidad real de desactivar el revoto en 3.3.0, no solo una hipótesis.** La variable está configurada a nivel de instancia/servidor; **no presumir** un switch diferente para cada elección. Demostrar la granularidad mediante dos instancias aisladas, una con revoto habilitado y otra con \`<deny-revote/>\`; validar tanto la UI como la recepción real de boletas por la API. Examinar posibles limitaciones de esa directiva, su compatibilidad con credenciales, pérdida de conexión y ataques de repetición.

**Actualizar la sección de revoto del ADR-001** durante la fase documental: sustituir “no se ha verificado que pueda desactivarse” por “la configuración de servidor admite \`<deny-revote/>\` en la versión 3.3.0; efecto y granularidad verificados en código, pendientes de validación funcional”. Mantener R1/R2 como decisión de producto/jurídica pendiente. No activar cambios al ADR fuera de una PR revisable.

Fuentes verificadas:
- https://github.com/glondu/belenios/blob/3.3.0/demo/ocsigenserver.conf.in
- https://github.com/glondu/belenios/blob/3.3.0/src/web/server/common/web_main.ml
- https://github.com/glondu/belenios/blob/3.3.0/src/web/server/common/web_persist.ml
- https://www.belenios.org/faq.html

## 3. Plan de ejecución rápido y secuencial (cinco hitos)

### H0 — Investigación reproductible sin ejecutar sistema

**Objetivo:** evitar dedicar tiempo a un adaptador imaginario.

1. Verificar \`git rev-parse HEAD\` de TheoGen y confirmar que sigue disponible el commit fijado de Belenios 3.3.0. Guardar hash de tag, commit, \`VERSION\`, licencia, \`INSTALL.md\`, \`doc/API.md\`, \`doc/auth.md\`, \`doc/cred.md\`, \`doc/tool.md\`, \`doc/web.md\`. Registrar cambios de API de 3.3 frente a master 4.0.0~dev, sin usar master en la PoC.
2. Crear \`doc/poc-belenios/01-factibilidad-y-contrato.md\` con endpoints verificados **en esa etiqueta**, tipo de autenticación, método HTTP, esquema esperado, permisos, estados, efectos laterales, tratamiento de fallos y \`If-Match\`. La API oficial se describe en \`doc/API.md\`, no asumir Swagger ni SDK público.
3. Revisar obligaciones AGPL y dependencias: redactar nota para revisión jurídica, no emitir dictamen definitivo.
4. Documentar matriz de roles/activos: operador TheoGen, administrador Belenios, operador de credenciales, servidor de credenciales, trustees, votante, auditor. Indicar qué confianza queda concentrada en la configuración mínima.
5. Producción de decisión **H0 GO/NO-GO**: si falta instalación/reproducción de tag, si hay bloqueo legal del uso del código o si hay funcionalidades no soportadas que invalidan las pruebas, documentarlo antes de programar.

### H1 — Instancia Belenios aislada y arranque documentado

**Requiere autorización explícita G1**. Trabajar en \`poc/belenios-3.3.0/\` o directorio comparable **aislado del backend electoral actual**, con README, \`docker-compose.poc.yml\` (si procede), configuración de ejemplo sin secretos, scripts reproducibles y \`.gitignore\`. No modificar \`docker-compose.yml\` ni el Nginx productivo de TheoGen.

1. Construir exactamente desde el commit fijado mediante Docker, **sin depender de una imagen desconocida/latest**. \`INSTALL.md\` de 3.3.0 ofrece \`contrib/docker/demo.Dockerfile\`; se trata expresamente de un laboratorio inseguro, NO producción.
2. Mostrar comandos mínimos oficiales para Linux y variante probada para Windows+WSL2/Docker Desktop **sin dar por intercambiables** \`--network host\` y \`-p\`. Verificar escucha real, loopback y puertos; bind solo localhost, firewall; nunca publicar email simulador o interfaz dummy en Internet.
3. El correo demo se registra en \`/static/mail.txt\` según \`INSTALL.md\`: tratarlo como contenedor de **credenciales de laboratorio** y no publicar logs/snapshots completos. No enviar mensajes de prueba a SMTP externo.
4. Persistencia de spool bajo volumen temporal; reinicio y restauración de datos ficticios; limpieza automática y reproducible. Verificar recursos CPU/RAM, tiempos de build y de arranque; registrar herramientas/versions, hashes y salidas sin secretos.
5. Probar health/no respuesta, rutas de acceso y flags mínimos. Si hay fallos, entregar guía de diagnóstico; no “resolver” deshabilitando controles de seguridad sin advertirlo.

**Evidencia H1:** README que reproduce arranque/parada en un entorno limpio; commit upstream fijado; lista de puertos; logs sanitizados; prueba de aislamiento; borrado seguro de datos de test.

### H2 — Elección íntegra de laboratorio, sin TheoGen

Crear **dos elecciones ficticias independientes, mínimo 8–12 unidades electorales cada una**, al menos dos listas/opciones y votos blanco/nulo **solo si sus semánticas se implementan explícitamente**. No utilizar RUT, email, nombres, ni dominios escolares reales. Utilizar identidades como \`votante01@ejemplo.test\`. Documentar si el proveedor del email dummy acepta ese dominio.

Flujo verificable:

1. Administrador crea borrador y carga padrón sintético; registra huella del padrón y configuración.
2. **Autoridad de credenciales diferente del operador de urna**, usando modalidad externa soportada. Ejercitar el protocolo \`credential operator\` y \`credential server\` de Belenios 3.3.0 cuando sea práctico; no atribuir independencia real a dos procesos bajo mismo root. Documentar los límites de la separación de simulación.
3. Configurar trustees externos preferentemente 2 de 3 si está soportado, con tres perfiles/custodias de prueba distintos; comprobar material público, custodia separada, ceremonia y revocación de material temporal al finalizar. Si se prueba solo un trustee primero, no atribuirle propiedades umbral.
4. Abrir; emitir votos en navegador original de Belenios; recoger trackers; comprobar inclusión pública sin conocer el contenido; no copiar credenciales a capturas o logs.
5. **Revoto habilitado:** dos sufragios con mismo derecho; validar que el último es el computado y el tracker previo deja de representar voto activo.
6. **Revoto deshabilitado:** otra instancia de servidor con \`<deny-revote/>\`; votar una vez y verificar rechazo del segundo tanto por navegador como por endpoint de envío compatible (no solo bloquear un botón).
7. Cerrar; realizar descifrado parcial de trustees; publicar escrutinio y comprobar cifras esperadas. Registrar fallas de ausencia de un trustee y umbral; no prometer recuperación cuando la pérdida impida escrutar.
8. **Verificación independiente obligatoria:** exportar el archivo electoral \`$UUID.bel\` y verificar en entorno separado con \`belenios-tool election verify --dir /path/to/election\`, según \`doc/tool.md\` de 3.3.0. Corroborar resultados con ensayo negativo: alterar una copia del artefacto público y demostrar detección o documentar qué manipulación no detecta el verificador.
9. Ensayar fallas: doble submit, refresh, sesión vencida, navegador cerrado, votante sin correo, credencial incorrecta, elección cerrada, caída/reinicio de servidor. Guardar comportamientos observados y errores reproducibles.

**Evidencia H2:** acta técnica de elección sintética, total de habilitados/emitidos, listados de trackers **sin vínculos personales**, versión de herramientas y stdout del verificador sanitizado, escenarios R1/R2 aprobados/rechazados.

### H3 — Contrato de integración y adaptador experimental, NO integración productiva

**No tocar rutas productivas de TheoGen.** Construir si H2 fue exitoso un adaptador de *laboratorio* independiente, preferentemente script/CLI pequeño o módulo \`poc/belenios-3.3.0/adapter/\` con pruebas de contrato. Priorizar pocas llamadas confirmadas frente a una arquitectura grande.

Interfaz mínima investigable desde el API 3.3.0:
- \`GET /api/configuration\` y lectura de estado/elección;
- autenticación administrativa y token Bearer en header (nunca query string, UI ni repositorio);
- \`POST /api/elections\`, \`GET/PUT /api/elections/$UUID/draft\`, \`GET/PUT /api/elections/$UUID/draft/voters\` conforme a \`doc/API.md\` y tipos \`serializable.atd\`;
- transición de estado soportada por \`POST /api/elections/$UUID\`, **verificar variantes reales de petición**;
- consulta de evidencias públicas, archivo \`.bel\`, descifrado/resultado y lectura de verificaciones;
- \`If-Match\` en mutaciones cuando sea aplicable, condiciones 401/403/404/409/412 y reintentos idempotentes.

**No asumir endpoints para crear credenciales privadas, OIDC passthrough, enlace familiar ni API de generación de actas chilenas.** Si el API no cubre un paso, identificar el procedimiento oficial por UI/CLI o señalar “intervención humana requerida”; no automatizar navegador con secretos sin revisión.

Construir mapeo conceptual mínimo:

\`TheoGen ElectionID\` → \`Belenios UUID\`; \`padrón validado de unidades electorales ficticias\` → \`voter identities aceptadas por Belenios\`; \`elección cerrada\` → \`resultado + prueba pública verificada\`; \`acta\` → \`datos estructurados derivados del resultado verificado\`.

**Nunca transferir desde TheoGen**: \`Vote.voter_id\`, \`candidate_id\` de votos individuales, RUT real, nombres de hijos/cursos, \`token_votacion\`, llaves privadas, secretos de credenciales, correo real, logs correlacionables. No usar el motor MVP como canal intermedio de sufragio.

### H4 — Ajuste funcional chileno y decisión sobre siguiente paso

1. **Voto familiar:** demostrar que el padrón puede tener **una identidad y una credencial por unidad familiar habilitada**, no dos credenciales independientes de miembros del hogar. Probar dos apoderados con emails distintos representando una única unidad, con registro de representante/gestión de discrepancia **fuera de Belenios**. No inferir derechos familiares a partir del mismo RUT, apellido o dirección. Para la PoC bastan IDs ficticios.
2. **Autenticación:** primero email/código de Belenios. Luego investigar OIDC de Google/Microsoft como autenticación, no como secreto del sufragio. Verificar qué rol admite \`<auth>\` vs \`<auth-export>\`, callbacks, claims, identificador de votante y elegibilidad. Si es imprescindible una demostración, usar IdP OIDC local con cuentas ficticias; no configurar OAuth contra cuentas reales ni almacenar ID tokens.
3. **Revoto:** documentar coste de separar instancias para política R1 (último sufragio) y R2 (primer voto irreversible), o demostrar otra opción respaldada en 3.3.0; nunca bloquear revoto únicamente con React/TheoGen.
4. **Actas:** producir prototipo de **plantilla y esquema de datos**, sin hacer pasar un PDF generado por acta jurídica válida. Campos: quórum, universo de unidades habilitadas, blancos/nulos explícitos, total de votos que cuentan, incidentes, fuente/hash \`.bel\`, verificación independiente, autoridades y firmas. Las reglas estatutarias deben aprobarse aparte.
5. **Privacidad/autohospedaje:** comprobar que los correos/RUT ficticios del laboratorio no se remiten a \`vote.belenios.org\`, rastrear DNS, SMTP, cookies, logs y terceros; documentar dependencias reales y obligaciones AGPL.
6. Realizar mini threat model de 8 amenazas: administrador malicioso, generador de credenciales comprometido, trustees coludidos, dispositivo votante malicioso, coacción remota, fuga de correo, fallo de servidor, correlación entre identidad/boleta.
7. Calcular costo de operación **a partir de medición**: build, tiempo de configuración por elección, CPU/RAM, disco, mensajería (simulada), horas de asistencia/trustees, infraestructura diferenciada y plan de respaldo. No inventar cifras CLP sin presupuesto.

## 4. Matriz obligatoria de pruebas y criterios GO/NO-GO

| ID | Prueba | Resultado requerido |
|---|---|---|
| BEL-01 | Instalación 3.3.0 fijada | Reproducible, hash, sin acceso público, correo falso |
| BEL-02 | Padrón de 8–12 unidades | Elección creada con lista aprobada y reproducible |
| BEL-03 | Credenciales independientes | Protocolo funcional o límite explícito registrado |
| BEL-04 | Trustees independientes | Escrutinio con aportes necesarios, sin centralizar clave |
| BEL-05 | Voto y tracker | Boletas aceptadas, inclusión verificable |
| BEL-06 | Revoto predeterminado | Último voto contabilizado |
| BEL-07 | \`<deny-revote/>\` en otra instancia | Segundo voto rechazado en backend, no solo UI |
| BEL-08 | Escenario familiar | Una única unidad habilitada; sin segundo sufragio |
| BEL-09 | Verificador externo | Archivo público y resultado aceptados por \`belenios-tool\` externo |
| BEL-10 | Tamper test | Alteración de copia detectada o límite documentado |
| BEL-11 | API | Endpoints/métodos/tipos realmente ejecutados; respuestas de error/If-Match |
| BEL-12 | Recuperación/fallos | Comportamientos medidos, sin pérdida silenciosa de boletas |
| BEL-13 | Datos personales | Cero RUT/correos reales y cero secretos en git/PR/log público |
| BEL-14 | Acta y participación | Concordancia con resultados verificados y regla familiar |
| BEL-15 | OIDC | Factibilidad documentada; ejecución opcional posterior y separada |

**NO-GO**: no se obtiene verificación independiente; revoto no coincide con política; secretos o materiales del padrón se exponen; roles simulados se presentan falsamente como independientes; faltan evidencias; integración necesita modificar criptografía; persiste tratamiento de datos reales.

**GO de PoC**: prueba cerrada, resultados reproducibles, limitaciones documentadas y recomendación para un siguiente diseño. **NO autoriza** uso vinculante, despliegue ni integración del motor en TheoGen.

## 5. Estructura sugerida de artefactos

\`\`\`text
doc/poc-belenios/
  00-mandato-spike-autohospedado.md   # esta instrucción
  01-factibilidad-y-contrato.md
  02-instalacion-aislada.md
  03-protocolos-y-matriz-pruebas.md
  04-resultados-verificacion.md
  05-compatibilidad-theogen-chile.md
  06-informe-go-no-go.md
poc/belenios-3.3.0/                  # SOLO tras G1
  README.md
  docker-compose.poc.yml
  .env.example
  .gitignore
  config/
  scripts/
  adapter/
  tests/
\`\`\`

No incluir archivos de credenciales privadas, claves trustee, secreto del operador, \`mail.txt\`, respaldos con material sensible ni datos completos del \`spool\` en PR o resultados.

## 6. Gobierno para ahorrar tiempo al agente

- **Tiempo invertido por etapas:** H0 primero; H1 solo si G1 autorizado; H2 antes de empezar un adaptador; H3 únicamente después de verificar una elección completa; H4 después de pruebas R1/R2 y auditoría. La prioridad es **reducir incertidumbre antes de programar**.
- Hacer checkpoints por hito, no una implementación monolítica. Un hito puede terminar en NO-GO; documentarlo en lugar de inventar workaround.
- Commits y PR pequeños: (a) documentación H0 y corrección ADR, (b) ambiente demo aislado H1, (c) escenarios/verify H2, (d) adaptador de contrato H3, (e) compatibilidad/decisión H4.
- No ejecutar simultáneamente agentes sobre los mismos archivos de Sprint 2. Mantener la PoC independiente hasta aprobación de integración; no fusionar automáticamente.
- Antes de cada herramienta externa, consultar instrucciones exactas fijadas en 3.3.0. Registrar URLs de documentación, archivos/funciones y SHA de upstream. Distinguir hechos de hipótesis y tests no ejecutados.
- Informe final por hito: comando, entorno, entrada ficticia, resultado esperado/observado, log sanitizado, bloqueo, decisión GO/NO-GO y siguiente decisión necesaria.

## 7. Prompt breve inicial para agente de programación

> Abre y lee íntegramente \`doc/poc-belenios/00-mandato-spike-autohospedado.md\`. Verifica la versión 3.3.0 de Belenios y HEAD real de TheoGen. Comienza exclusivamente por H0, con evidencia verificable de API, instalación, licencia, roles y la directiva \`<deny-revote/>\`. Redacta \`doc/poc-belenios/01-factibilidad-y-contrato.md\` y propone el entorno aislado. No construyas, ejecutes ni integres Belenios hasta que reciba autorización explícita para el Gate G1. Una vez aprobada G1, avanza H1 y H2 usando solo datos falsos, luego presenta evidencia de verificación externa y políticas R1/R2; no modifiques el motor de voto TheoGen.

## 8. Referencias directas de versión fijada

- \`VERSION\`: https://github.com/glondu/belenios/blob/3.3.0/VERSION
- \`INSTALL.md\`: https://github.com/glondu/belenios/blob/3.3.0/INSTALL.md
- \`doc/API.md\`: https://github.com/glondu/belenios/blob/3.3.0/doc/API.md
- \`doc/auth.md\`: https://github.com/glondu/belenios/blob/3.3.0/doc/auth.md
- \`doc/cred.md\`: https://github.com/glondu/belenios/blob/3.3.0/doc/cred.md
- \`doc/tool.md\`: https://github.com/glondu/belenios/blob/3.3.0/doc/tool.md
- \`demo/ocsigenserver.conf.in\`: https://github.com/glondu/belenios/blob/3.3.0/demo/ocsigenserver.conf.in
- \`web_main.ml\`: https://github.com/glondu/belenios/blob/3.3.0/src/web/server/common/web_main.ml
- \`web_persist.ml\`: https://github.com/glondu/belenios/blob/3.3.0/src/web/server/common/web_persist.ml
- Documentación oficial: https://www.belenios.org/instructions.html y https://www.belenios.org/faq.html

**Control final:** esta propuesta no demuestra seguridad ni otorga autorización para implementar un motor productivo. El ADR-001 sigue pendiente de decisión.
