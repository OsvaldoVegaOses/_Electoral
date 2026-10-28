# H0 — Factibilidad y contrato de Belenios 3.3.0 autohospedado

**Fecha:** 2026-10-28. **Resultado:** GO documental condicionado para someter G1 a decisión; **H1 no autorizado ni iniciado**. ADR-001 permanece PROPUESTO.

Este informe satisface H0 del [mandato](00-mandato-spike-autohospedado.md). Demuestra disponibilidad de fuentes y comportamiento expresado en código; no demuestra instalación, respuestas HTTP observadas, seguridad operacional ni una elección verificada. No se compiló ni ejecutó Belenios, Docker, sus tests o `belenios-tool`; tampoco se creó un adaptador.

## 1. Procedencia y alcance de la evidencia

| Referencia | Valor verificado |
|---|---|
| Repositorio TheoGen | `OsvaldoVegaOses/_Electoral` |
| HEAD del workspace del usuario | `65c164c7bb4073d5250c04d8f8cb40095a759ffb`, rama `fix/s2-c-pii-privacy-tokens`, con cambios locales de Sprint 2 |
| Mandato actualizado en GitHub | Rama `docs/spike-poc-belenios-33`, commit `de2e568464bb3bc89ea788de95f29ef3ec128b77` |
| Base de esta entrega | Worktree documental separado desde ese commit; no se cambió la rama del workspace original |
| Base histórica citada por el mandato | `1f27936992cd65e001bcf61e1234af25f2c15e78`; no confundir con el HEAD actual |
| Contexto | `doc/motor/propuestas_motor.md`; corrección propuesta en el ADR canónico `doc/adr/001-motor-de-votacion.md` |
| Instrucción adicional | `doc/poc-belenios/agente.md` local; su consulta remota en la rama documental devolvió 404 |
| Espejo consultado | `https://github.com/glondu/belenios`; el proyecto identifica GitLab como upstream |
| Tag anotado `3.3.0` | Objeto `2f0c5eb950d964baeea95f81ff6db7c418020ba5` |
| Commit desreferenciado | **`337887bd1862c7cd057080b530fd80941bfc3c69`** |
| `VERSION` | `3.3.0` |
| Firma del tag | Existe firma PGP; GitHub informa `verified=false`, `reason=unknown_key`. No se verificó localmente con una clave confiable ni se cotejó con GitLab |
| Comparación exclusivamente documental | `master` fijado al snapshot `8888045a7650df5241a76ae75128ebde61e83904`, `VERSION=4.0.0~dev`; no se cambió el checkout de 3.3.0 |

Se adquirió una copia temporal de las fuentes con `core.autocrlf=false`, sin construir un entorno H1. El [manifiesto H0](evidencias/h0-2026-10-28.json) conserva blobs Git, SHA-256 de bytes de las fuentes consultadas, referencias, comprobaciones estáticas y límites. Los identificadores Git fijan contenido; no sustituyen la verificación de autoría del tag.

### Reproducción de la investigación (sin ejecutar Belenios)

En una terminal PowerShell y directorio temporal nuevo:

```powershell
git -c core.autocrlf=false clone --branch 3.3.0 --depth 1 https://github.com/glondu/belenios.git belenios-fuentes-h0
git -C belenios-fuentes-h0 rev-parse refs/tags/3.3.0
git -C belenios-fuentes-h0 rev-parse 'refs/tags/3.3.0^{}'
Get-Content -LiteralPath belenios-fuentes-h0/VERSION
Get-FileHash -Algorithm SHA256 -LiteralPath belenios-fuentes-h0/doc/API.md
git -C belenios-fuentes-h0 fetch --depth 1 origin 8888045a7650df5241a76ae75128ebde61e83904
git -C belenios-fuentes-h0 diff 337887bd1862c7cd057080b530fd80941bfc3c69 8888045a7650df5241a76ae75128ebde61e83904 -- doc/API.md
```

Comparar cada archivo del manifiesto con `git rev-parse '<commit>:<ruta>'` y `Get-FileHash`; un cambio de hash invalida esa comparación. No ejecutar `make`, scripts upstream o contenedores para reproducir H0.

El comprobador adjunto lee blobs Git sin ejecutar código upstream. Desde el worktree de esta PR, con ambas referencias de Belenios descargadas y la base documental TheoGen disponible:

```powershell
python doc/poc-belenios/evidencias/verificar-fuentes.py --belenios <ruta-a-belenios-fuentes-h0> --theogen .
```

Usar rutas reales en lugar del marcador. Comprueba 51 fuentes fijadas, 4 de comparación, 3 de la base TheoGen, tag/commit, diff de API y 19 condiciones estáticas centrales. No valida firma PGP, endpoints, build ni criptografía.

## 2. Instalación: receta disponible y reproducción pendiente

Fuentes: [INSTALL.md][S1], [Dockerfile demo][S2], [Dockerfile base][S3], [bootstrap][S4], [configuración demo][S5], [arranque][S6] y [correo simulado][S7], todas en el commit fijado.

La receta oficial Linux contiene `make clean`, `docker build -f contrib/docker/demo.Dockerfile -t belenios .` y `docker run --rm --network host -it belenios`. Se transcribe como referencia documental: **no fue ejecutada y requiere G1**. `INSTALL.md` declara expresamente que la demo no es para producción.

Hallazgos que H1 debe resolver antes del primer arranque:

1. El Dockerfile parte de `glondu/beleniosbase:20260425-1`, una etiqueta externa sin digest. Fijar el commit de la aplicación no fija esa imagen ni garantiza una build reproducible. Upstream ofrece construir la base con el target `beleniosbase` de `contrib/docker/gitlab-ci.Dockerfile`; este parte de `debian:13` y hace `apt-get update/upgrade`, también variables. Registrar digest, plataforma, paquetes, fuentes descargadas y hash de imagen resultante. No reemplazar silenciosamente una dependencia desaparecida ni actualizar a master.
2. El bootstrap fija OCaml `5.4.1`, OPAM `2.5.1` y el repositorio OPAM `045748b2d8c25925135981a8892305b10706ca06`; verifica el tarball de OPAM. Requiere overlay `vendor/opam-overlay`, sistema POSIX y dependencias nativas: compilador C, GMP, libsodium, OpenSSL, SQLite, sendmail, npm y binaryen, entre otras. Los archivos `.opam` expresan restricciones de bibliotecas, no una garantía sobre todos los artefactos externos. El Dockerfile base usa `--disable-sandboxing` para OPAM: registrar ese hecho y aislar la build.
3. La demo ejecuta `make build-debug-server`; el modo restringido prohíbe debug. No atribuir a esta demo las garantías de `<restricted/>`, ni añadirlo esperando que funcione sin cambiar el procedimiento de compilación aprobado.
4. El servidor demo escucha **`127.0.0.1:8001` dentro de su espacio de red**. En Linux, `--network host` comparte la red del host. Publicar `-p 127.0.0.1:8001:8001` con una red bridge no hace accesible por sí solo un proceso que solo escucha el loopback del contenedor. En Windows/Docker Desktop/WSL2 debe elegirse y probarse una topología concreta. Propuesta para G1: Linux/WSL2 aislado o bridge con escucha interna ajustada en configuración local y publicación solo en loopback del host; no abrir interfaz pública. No hay variante Windows probada en H0.
5. `BELENIOS_SENDMAIL=tests/sendmail_fake_to_static.sh` redirige el correo a `_run/usr/share/belenios-server/static/mail.txt`, servido como `/static/mail.txt`. Puede contener OTP, credenciales y enlaces con capacidades; no capturarlo ni incluirlo en Git, PR o logs de evidencia. No conectar SMTP externo.
6. `demo/run-server.sh` prepara estado bajo `BELENIOS_VARDIR` (por defecto `_run` en el árbol compilado), con spool, cuentas, base de sesiones, uploads y logs. Proponer volúmenes temporales separados por instancia; preservar también configuración y datos de credenciales. Una copia solo del spool no demuestra restauración íntegra. Medir reinicio y recuperación antes de afirmar continuidad.
7. La configuración incluye autenticación dummy, cuentas demo, endpoints de credenciales locales y capacidades de mantenimiento de ejemplo. Sustituir material de ejemplo en H1 sin publicarlo. Ajustar coherentemente `public-url`, URL del servidor de credenciales y sus allowlists; la configuración de una sola instancia no sirve directamente para dos procesos con puertos distintos.

**Propuesta de entorno, pendiente de aprobación:** dos procesos Belenios separados (A: revoto habilitado; B: `<deny-revote/>`), puertos de host propuestos 8001/8002 solo loopback, volúmenes y perfiles de navegador distintos; servidor de credenciales C con administración diferenciada, tres custodias de trustees de laboratorio y verificador en otro entorno. Ningún archivo de `poc/` ni compose se crea en H0. Bajo un mismo root la separación será una simulación operacional; no independencia frente al administrador de infraestructura. No se midieron CPU, RAM, disco, tiempos ni costos.

## 3. Contrato HTTP de la versión fijada

### 3.1 Fuentes, autenticación y formatos

Contrato documental: [doc/API.md][S8]. Contraste de implementación: [router][S9], [borradores][S10], [elecciones][S11], [tipos API][S12], [serialización del borrador][S13] y [tipos comunes][S14]. La ruta `src/common/api/serializable.atd` citada por `doc/API.md` **no existe en 3.3.0**; la correcta es `src/web/api/serializable.atd`.

- Todas las rutas de las tablas son relativas a **`/api/`**. `U` significa UUID opaco Belenios (la demo configura longitud 14); no imponer formato UUID RFC de TheoGen. `H` es hash **hexadecimal** para `objects/H`; un tracker en Base64Compact requiere conversión, no interpolación directa.
- Administrador: login web y `GET /api-token`, o `POST /api/login/<servicio>` cuando ese backend implementa login programático. Enviar `Authorization: Bearer <token>` exclusivamente como header. El token se guarda en memoria, vence en 24 horas; se invalida al cerrar esa sesión web, mediante `DELETE /api/login` o al reiniciar. No existe aquí un token permanente de servicio ni se demuestra refresh automático.
- El backend dummy acepta `auth_dummy_info={username}`; password administrativo, `auth_password_info={username,password}`. No generalizar ese POST a email, CAS u OIDC: sus dispatchers/flujo deben verificarse por backend; el dispatcher OIDC de 3.3.0 devuelve 404. El login humano por navegador sigue siendo una vía soportada para obtener el token. No automatizar secretos en el navegador dentro de H0.
- Autoridad de credenciales y trustee: capacidades distintas del token administrativo, con comprobaciones propias y alcance de elección/fase. Los enlaces oficiales pueden contener capacidades en fragmentos; proteger también historial, capturas y copias. El futuro adaptador no debe pasar su token administrativo por URL.
- ATD serializa variantes sin argumento como cadenas (`"Close"`) y variantes con argumento como arrays (`["Seal",true]`). No asumir JSON de master ni un objeto `{action: ...}`. `unit` de respuesta normalmente es **HTTP 200 `{}`**, no 204. Crear elección retorna HTTP 200 con UUID como cadena JSON, no 201.

### 3.2 Administración y borrador

**A:** administrador propietario; **C:** capacidad de autoridad de credenciales; **T:** capacidad de trustee; **P:** sin token administrativo. **M:** código llama a `handle_ifmatch`; **—:** no se encontró ese control en la operación (no asumir soporte por el texto general de API). Resultados y errores son lecturas de código, **no respuestas HTTP ejecutadas**.

| Método y ruta | Autorización | Entrada → salida | Estado, efecto y errores relevantes | If-Match |
|---|---|---|---|---|
| GET `configuration` | P | vacío → `configuration` | Versión/build, `api_version=6`, grupos, métodos exportados, idiomas y límites. No revela `deny_revote` | — |
| GET `readonly` | P | vacío → bool | Mantenimiento de almacenamiento; no health integral | — |
| PUT `readonly` | Token específico de servidor | bool → `{}` | Compara hash del Bearer con configuración; cambia mantenimiento global, 401 si falla. Fuera del adaptador | — |
| POST `login/<servicio>` | Backend `<auth>` | JSON del backend → `{token,expiration}` | Depende del servicio; dummy/password en laboratorio; 404 si no implementado | — |
| DELETE `login` | Bearer presente | vacío → `{}` | Invalida ese token; no revoca todas las sesiones | — |
| GET / PUT `account` | Administrador autenticado | vacío / `api_account` → cuenta / `{}` | PUT permite ciertos datos; no cambiar id, dirección o identidad del método; 400 `CannotChange` | PUT M |
| GET `elections` | Administrador autenticado | vacío → `summary_list` | Lista elecciones de su cuenta; no inventario de toda la instancia | — |
| POST `elections` | Administrador autenticado | `draft` → cadena UUID | Crea borrador; 403 si nuevas elecciones no permitidas; 400 en validación | M sobre GET de la lista |
| GET `elections/U/draft` | P; vista A según token | vacío → `draft` | Borrador público existente; token inválido/ajeno puede devolver 404 | — |
| PUT `elections/U/draft` | A | `draft` → `{}` | Edición completa del borrador; owners debe incluir cuenta; idioma, grupo, booth y campos congelados se validan | M |
| POST `elections/U/draft` | A | `draft_request` → `{}` | Validación y marcas de preparación; puede iniciar protocolo externo asíncrono. Ver §3.4 | M |
| GET `elections/U/election` | P | vacío → parámetros JSON | Funciona también como vista de parámetros del borrador; no implica clave electoral final antes de validar | — |
| GET `elections/U/draft/election` | Documentado P | vacío → JSON según documento | **Sin rama de despacho en código 3.3.0**: se espera 404. Usar `/elections/U/election`; confirmar en BEL-11 | — |
| GET `elections/U/draft/voters` | A o C | vacío → `voter_list` | Lista completa sensible; 401 si falta token, 404 si no autorizado | — |
| PUT `elections/U/draft/voters` | A | `voter_list` → `{}` | Reemplaza lista; 403 si ya se inició/recibió generación de credenciales; 400 por formato, duplicados o peso | M |
| POST `elections/U/draft/voters` | A | `["Import",UUID]` → `{}` | Importa otra elección propia; no usar datos históricos reales | M |
| GET `elections/U/draft/credentials/token` | A | vacío → capacidad C | Puede dar 404 si autoridad `server`; salida secreta, no loguear | — |
| GET `elections/U/draft/credentials/public` | P | vacío → lista de strings | 404 si aún no disponible | — |
| POST `elections/U/draft/credentials/public` | C; caso especial A | lista de strings → `{}` | C sube claves públicas. A con `[]` puede iniciar generación por servidor; no es emisión genérica independiente. 403 si ya hay generación/credenciales | — |
| GET `elections/U/draft/credentials/private` | A | vacío → `private_credentials` | Existe solo si material disponible; 404 en otro caso. No usar como diseño de independencia ni almacenar su salida | — |
| GET / POST `elections/U/draft/trustee` | T | vacío / JSON criptográfico → `trustee_status` / `{}` | Básico o ceremonia Pedersen por pasos; 401 capacidad incorrecta; errores de clave/paso | — |
| GET `elections/U/draft/trustees` | P o A | vacío → `draft_trustees` | Vista pública o administrativa; esta última puede incluir tokens. No publicar respuesta A | — |
| POST `elections/U/draft/trustees` | A | `trustees_request` → `{}` | Add, Import, SetBasic, SetThreshold, Reset; una operación no completa la ceremonia | M sobre vista A |
| DELETE `elections/U/draft/trustees/<dirección>` | A | vacío → `{}` | Elimina trustee del borrador; dirección URL-encoded; 404 si ausente | — |
| GET `elections/U/draft/status` | A | vacío → `draft_status` | Número de votantes, credenciales/trustees listos y restricciones; comprobar antes de validar | — |

### 3.3 Elección validada, sufragio y evidencia

| Método y ruta | Autorización | Entrada → salida | Estado, efecto y errores relevantes | If-Match |
|---|---|---|---|---|
| GET `elections/U` | P | vacío → `election_status` | Estado, autenticación, sellado y fechas de archivo/borrado; no es resultado ni prueba | — |
| POST `elections/U` | A | `admin_request` → `{}` | Abrir/cerrar, escrutar, mezclar, publicar, archivar, sellar; ver §3.4 | M |
| DELETE `elections/U` | A | vacío → `{}` | Borrado destructivo, incluido borrador; no usar como reintento/compensación | — |
| GET `elections/U/audit-cache` | P | vacío → `audit_cache` | Huellas/cache de comprobación; no sustituye verificador | — |
| GET `elections/U/sealing-log` | A | vacío → flujo de texto | Evidencia de sellado; acceso restringido | — |
| GET / PUT / DELETE `elections/U/logo` | P / A / A | vacío / PNG / vacío → PNG / `{}` / `{}` | DELETE aparece en código aunque no en API.md; PUT máximo 10240 bytes; 403 sellada, 413 exceso | — |
| GET `elections/U/trustees` | P | vacío → trustees | Información pública; umbral de borrador incompleto puede dar 412 | — |
| GET / PUT `elections/U/automatic-dates` | P / A | vacío / `election_auto_dates` → fechas / `{}` | También admite borrador; PUT 403 si sellada | PUT M |
| GET `elections/U/voters` | A | vacío → `voter_list` | Padrón sensible; no publicarlo | — |
| GET `elections/U/records` | A | vacío → `{date,username}[]` | Participación correlacionable; no incluir en expediente público | — |
| GET `elections/U/trustee` | T | vacío → `tally_trustee` | En `EncryptedTally`; puede contener material cifrado de la parte Pedersen. No publicar | — |
| POST `elections/U/trustee` | T; capacidad de mezcla según fase | prueba JSON → `{}` | Descifrado en `EncryptedTally`: 409 aporte ya recibido, 400 inválido. Mezcla en `Shuffling`: 403 capacidad incorrecta. Otra fase: 412 | — |
| GET `elections/U/nh-ciphertexts` | P | vacío → cifrados no homomórficos | Solo aplicable a esa papeleta/fase; 404 si no hay elección | — |
| GET `elections/U/encrypted-tally` | P | vacío → escrutinio cifrado | 404 si no disponible; no es resultado en claro | — |
| GET `elections/U/shuffles` | A | vacío → `shuffles` | Requiere `Shuffling`; puede incluir capacidades | — |
| POST `elections/U/shuffles/<dirección>` | A | `"Skip"` o `"Select"` → `{}` | Selección/omisión de mezclador; no equivale a aportar la mezcla | — |
| GET `elections/U/partial-decryptions` | A | vacío → estado/umbral | `EncryptedTally`; incluye capacidades de trustees y puede generarlas/persistirlas. GET no necesariamente sin efecto lateral | — |
| GET `elections/U/objects/H` | P | vacío → objeto JSON exacto | Hash hexadecimal; 404 si ausente. Obtener/verificar objeto apuntado por `roots.result` para resultado | — |
| GET `elections/U/archive-header` | P | vacío → `archive_header` | Cabecera necesaria para reconstruir `.bel`; 404 ausente | — |
| GET `elections/U/last-event` | P | vacío → `last_event` | Cabeza de cadena de eventos; fijarla al descargar | — |
| GET `elections/U/roots` | P | vacío → `roots` | Referencias de resultado, tally y eventos, no cifras verificadas por sí solas | — |
| GET `elections/U/ballots` | P | vacío → `ballots_with_weights` | Objeto hash de boleta activa → peso; descarta boletas sustituidas al construir la vista | — |
| POST `elections/U/ballots` | P en prevalidación | boleta cifrada canónica → `401 {state}` o error | Verifica estructura/prueba/credencial/duplicado y crea estado de autenticación. **No confirma voto aceptado**; ver §3.5 | — |
| GET `cast-result/<estado>` | Poseedor del estado | vacío → `cast_result` | 404 sin resultado; `Ok` con tracker/revote/confirmación o `Error` con causa. El estado es sensible | — |
| GET `elections/U/archive.zip` | A | vacío → ZIP confidencial | Contiene `public/U.bel` **y** `restricted/voters.txt`, `restricted/records`. No entregarlo completo al auditor público | — |

No se encontró un endpoint genérico `/result` ni una ruta API `.bel` que deba suponerse. `belenios-tool archive pull` reconstruye el archivo público mediante `archive-header`, `last-event` y `objects/H` ([código][S22]); la UI de 3.3.0 enlaza «public data» a `last-event` ([footer][S23]). La descripción de descarga de `doc/web.md` es insuficiente para asumir una URL directa.

### 3.4 Tipos, estados y transiciones

`draft` contiene `version` (versión criptográfica, **no** string `3.3.0`), `owners:int[]`, `questions:template`, `languages:string[]`, `booth:int`, `group:string` y opcionales `contact`, `authentication`, `cred_authority_info:{server,operator}`. `template` contiene nombre, descripción, preguntas y opcionales de administrador/autoridad. Consultar `configuration` y `account` para valores compatibles. `voter_list` es un array JSON homogéneo de strings de identidad o de objetos `{address?,login?,weight?}`; se admiten logins sin dirección en el tipo, pero eso no demuestra que email/OTP funcione sin correo. No enviar un CSV crudo como body esperando el parser ATD.

Para ilustrar solo el padrón sintético (no se envió):

```json
[
  {"address":"votante01@ejemplo.test","login":"unidad01"},
  {"address":"votante02@ejemplo.test","login":"unidad02"}
]
```

`draft_request` acepta `"SetDownloaded"`, `"ValidateElection"`, `"SetCredentialAuthorityVisited"`, `"SetVoterAuthenticationVisited"`, `["SetTrusteesSetupStep",n]`, `"InitiateCredentialAuthorityProtocol"`. La última inicia trabajo asíncrono: HTTP 200 no prueba que el servidor externo generó ni entregó credenciales. Leer status, certificado y evidencias de entrega simulada.

`trustees_request`: `["Add",objeto]`, `["Import",UUID]`, `"SetBasic"`, `["SetThreshold",n]`, `"Reset"`. Completar certificados y pasos Pedersen con cada trustee antes de validar.

`admin_request`: `"Open"`, `"Close"`, `"ComputeEncryptedTally"`, `"FinishShuffling"`, `"ReleaseTally"`, `"Archive"`, `["Seal",bool]`. El código de [validación filesystem][S24] deja la elección **Closed**, elimina el borrador y las credenciales privadas temporales; contradice el texto de `doc/web.md` que describe apertura inmediata. Flujo esperado desde código:

```text
Draft --ValidateElection--> Closed --Open--> Open --Close--> Closed
Closed --ComputeEncryptedTally--> EncryptedTally                  (homomórfica)
Closed --ComputeEncryptedTally--> Shuffling --FinishShuffling--> EncryptedTally (NH)
EncryptedTally --aportes requeridos + ReleaseTally--> Tallied
```

`Open`/`Close` solo operan sobre Open/Closed, se rechazan si sellada y borran fechas automáticas de apertura/cierre. Sellar no significa abrir. No usar Archive o DELETE para corregir un timeout: son operaciones con consecuencias de conservación/borrado. La exactitud de todas las transiciones queda para BEL-11.

### 3.5 Flujo real de voto y rechazo de revoto

1. La UI cifra/firma localmente la selección. `POST /api/elections/U/ballots` recibe **la boleta**, no un `candidate_id`, una credencial privada o un token TheoGen. Si pasa prevalidación responde 401 con estado; una boleta duplicada puede fallar antes de autenticar.
2. Se continúa el flujo web en `/actions/voter-login?state=...`, se autentica al elector según la elección y se confirma en `/actions/confirm?state=...`. Son rutas web de 3.3.0, no un API Bearer genérico de voto. Usar la UI oficial o su modo avanzado; registrar el resultado final sin exponer el estado.
3. [site_voter.ml][S19] llama a `Api_elections.cast_ballot`; ahí se comprueban padrón, fase abierta y las condiciones de gracia aplicables. [web_persist.ml][S18] comprueba identidad/peso/credencial, concurrencia de la boleta prevalidada y `deny_revote`, antes de añadir el evento y actualizar las asociaciones.
4. Consultar el resultado con `GET /api/cast-result/<estado>` y corroborar tracker en la vista activa/archivo público. Un 401 inicial esperado no es rechazo final de revoto; un 200 de otra etapa tampoco es prueba de aceptación.

El ensayo BEL-07 por API debe enviar una **nueva boleta válida con la misma credencial**, completar autenticación/confirmación y observar `Error RevoteNotAllowed`; reenviar idénticos bytes puede dar `DuplicateBallot`, que solo demuestra detección de duplicados. Comparar cabeza de eventos, lista activa y resultado final para comprobar que el segundo voto no se contó. Si se pierde respuesta, no generar silenciosamente otro sufragio.

### 3.6 If-Match, errores y reintentos

El [helper][S15] compara `If-Match` con SHA-256 de **los bytes exactos** que produce su GET, codificado en Base64 estándar sin `=` (Base64Compact). No es hexadecimal, Base64URL ni JSON vuelto a formatear; [Hash.to_b64][S25] fija esa codificación. No suponer ETag o añadir comillas por costumbre HTTP. Conservar por separado la respuesta pública y la vista administrativa cuando difieren, especialmente trustees.

La tabla identifica cobertura real. No se usa `handle_ifmatch` en todas las mutaciones, pese a la formulación general de API.md: DELETE de elección/trustee, envío de boleta, credenciales, aportes y mezclas no reciben esa protección mediante ese helper. Exigir If-Match donde existe; donde no existe, diseñar lectura posterior y serialización del operador, sin afirmar exclusión transaccional demostrada.

| Resultado previsto por código | Interpretación para laboratorio |
|---|---|
| 400 | Parseo/tipo inválido o `request_status={code,status,error}`; puede incluir `ValidationError`, `CannotChange`, `NotInExpectedState`, `CastError`. No reintentar sin corregir causa |
| 401 | Falta/expiración de capacidad o token; **excepción esperada**: inicio del flujo `POST ballots`. Distinguir por ruta y body |
| 403 | Operación prohibida en fase/configuración, sellado o credenciales ya iniciadas; no resolver quitando controles |
| 404 | Ausencia y, en helpers de borrador, ocultación frente a token inválido/ajeno. No demuestra que el UUID no exista |
| 405 | Método no implementado; algunos accesos sin permiso caen en esta rama de borrador |
| 409 | Aporte de descifrado ya realizado; no es la respuesta universal a transición incorrecta |
| 412 | Hash If-Match diferente **o** fase/prerrequisito no admitido en rutas como trustee; inspeccionar contexto |
| 413 / 500 / 502 / 503 | Tamaño, fallo interno, dependencia de credenciales o mantenimiento; sanitizar body y reconciliar estado antes de continuar |

No se identificó clave de idempotencia para crear elección o votar. Un timeout después de POST tiene resultado **desconocido**: detener la repetición, cotejar lista de elecciones/configuración/eventos/trackers y registrar resolución. Renovar token no autoriza repetir automáticamente una mutación. If-Match evita algunos conflictos, no demuestra entrega exactamente una vez.

### 3.7 Protocolo de credenciales y mensajería

| Método y ruta | Esquema y autorización real en código | Efecto / control |
|---|---|---|
| POST `credentials/server` | `credentials_request`: `NewRequest` con URL/UUID/info/token/admin_id; `Validate` con UUID/token/metadata; `Resend` con UUID/seed/spec | Autorización en contenido, allowlists y comprobación de semilla/capacidad; no equivale a token A. NewRequest/Resend pueden ser asíncronos |
| POST `credentials/belenios` | `{certificate,token,public_credentials}` | Callback a urna; compara capacidad del borrador y sube certificado/claves públicas; 403 capacidad distinta |
| GET `credentials/server/credits/U` | `Authorization: Bearer <semilla del operador>` | No token A: verifica clave derivada de semilla, devuelve créditos de reenvío; 401 incorrecta. Tratar ese header como secreto crítico |
| POST `send-message/internal`, `external`, `default` | `message_payload` de `src/web/server/messages/serializable.atd` | Requiere mensajería interna configurada y HMAC en payload en 3.3.0; tiempo y cache contra repetición; 403 inválido/repetido, 405 si no configurado, 503 fallo. No es envío libre por llamarse «anybody» en API.md |

Las credenciales privadas, la semilla, los tokens en payloads y las respuestas administrativas se excluyen del expediente público. Este contrato identifica capacidades; **no las invoca** ni añade automatización de recuperación.

## 4. Revoto: evidencia y granularidad

La configuración de servidor admite `<deny-revote/>` en 3.3.0; efecto y granularidad verificados en código, pendientes de validación funcional:

- [demo/ocsigenserver.conf.in][S5]: directiva comentada, explica que deshabilita revoto.
- [web_config.ml][S16]: `deny_revote` es una referencia global inicializada en false.
- [web_main.ml][S17]: el parser de configuración la establece en true; no es un campo de `draft` ni de metadata electoral.
- [web_persist.ml][S18]: cuando existe una boleta previa de la credencial, retorna `RevoteNotAllowed` si la referencia global es true. La misma función se alcanza desde la confirmación web/API descrita; no es un bloqueo de botón.
- [public_archive.ml][S20] construye la vista activa descartando credenciales ya vistas al recorrer eventos desde el más reciente; el tally usa la última boleta por credencial. **El archivo append-only conserva eventos anteriores**: «deja de ser voto activo» no significa borrado de toda evidencia histórica.

No se encontró switch soportado por elección ni API para cambiarlo. H2 requiere dos procesos con configuración/almacenamiento separados, evitando conflicto de una variable global entre configuraciones alojadas en un proceso. R1/R2 continúa siendo decisión de comisión y asesoría jurídica. Una corrección documental del ADR no selecciona ninguna política.

Riesgos específicos por probar: doble submit con idénticos bytes frente a nueva boleta; dos confirmaciones concurrentes (`ExpiredBallot` u otro error observado); respuesta perdida después de aceptación; reinicio que pierde estados de autenticación pero conserva urna; reenvío de la misma credencial sin crear otra; cierre automático y período de gracia. No se acredita irreversibilidad frente a administrador malicioso o restauración indebida por existir el flag.

## 5. Autoridades, autenticación y activos

Fuentes: [doc/cred.md][S26], [doc/auth.md][S27], [OIDC][S28], [validación][S24] y [test upstream umbral][S29] (leído, no ejecutado).

| Rol | Activos / acciones | Separación y límite |
|---|---|---|
| Operador TheoGen | Padrón privado, regla familiar y correspondencia con IDs aleatorios de elección | No participa aún en PoC; no transfiere RUT, vínculos familiares, votos históricos, `token_votacion` ni cuentas reales |
| Administrador electoral Belenios | Token A, configuración, padrón sintético, abrir/cerrar/publicar | No custodiar semilla ni suficientes secretos de trustees; operador de infraestructura puede acceder a su estado |
| Operador de credenciales | Semilla, certificado, autorización de reenvíos | Actor diferente del administrador de urna; comprueba UUID, longitud de padrón, hash público y certificado |
| Servidor de credenciales | Generación/distribución simulada; credenciales privadas cifradas a largo plazo | Conoce semilla/privadas durante generación y reenvíos; requiere no compromiso en esas ventanas. Mismo root no es independencia |
| Trustee | Su secreto, certificado y contribución de descifrado | Tres custodias/profiles distintos; publicar solo material público/pruebas. Pérdida suficiente de partes impide escrutinio |
| Votante | Credencial privada y autenticación; tracker público | Credencial de firma distinta de OTP/login; no publicar relación identidad–tracker |
| Auditor / monitor | Fuentes fijadas, archivo público, hashes, anclaje de eventos y resultado esperado | Verifica en otro entorno sin token A ni padrón privado; no usar ZIP confidencial como artefacto público |

El protocolo 3.2+ separa operador y servidor: el servidor genera semilla y credenciales, entrega semilla al operador, sube certificado/credenciales públicas, y tras validación distribuye privadas; almacena privadas cifradas y elimina semilla/plaintext de su operación honesta. Recuperar requiere presentar semilla, crea una ventana sensible y tiene créditos/límites. El código de `credentials/server` y `credentials/belenios` respalda este flujo; no hay una promesa genérica de reemisión sin consecuencias. La alternativa manual por UI/CLI existe, con custodia/distribución a cargo de la autoridad.

**Umbral:** `SetThreshold`, estados Pedersen y test `tests/tool/demo-threshold.sh` con 3 autoridades/umbral 2 respaldan factibilidad estática de 2 de 3. La validación del servidor añade además una clave **server** (`Single` junto a `Pedersen`); no describirlo como ausencia total de material de descifrado en la urna. Ese componente no basta por sí solo para descifrar sin el umbral externo. Verificar participantes efectivos, claves públicas, custodia y disponibilidad del servidor al ensayar ausencias. Una ejecución con un trustee básico no acredita propiedades umbral.

**Autenticación:** `<auth>` configura administradores; `<auth-export>` métodos elegibles para votantes. El ejemplo exporta email/OTP, dummy y CAS; las contraseñas estáticas de votantes fueron eliminadas en 3.3.0 según RELEASE_NOTES. `doc/web.md` y páginas web generales conservan instrucciones antiguas: para esos puntos prevalecen release/código fijados. OIDC usa discovery, callback `/auth/oidc`, authorization code y userinfo; toma `email` como login si existe, o `sub` si no. No se encontró campo `email_verified` en su tipo userinfo: no presumir validación de correo verificado ni equivalencia automática con padrón. Google/Microsoft requerirían estudiar claims y proveedor concreto; no se registraron clientes ni se usaron cuentas reales. La elegibilidad se comprueba aparte.

**Unidad familiar propuesta:** una unidad sintética → un login y una credencial; dos apoderados se resuelven mediante representante fuera de Belenios. No asignar dos credenciales esperando que pesos o coincidencias de correo impidan doble sufragio. No se verificó compatibilidad jurídica ni se diseñó un protocolo criptográfico familiar.

## 6. Licencia y dependencias: nota para revisión jurídica

[README][S30] declara AGPL-3.0-or-later para código interno, con excepción de compilación/enlace/uso de OpenSSL. [COPYING][S31] contiene la licencia, incluida sección 13 para versiones modificadas con interacción remota. Documentar avisos, modificaciones, distribución de fuente correspondiente y forma de ofrecerla a usuarios; `doc/web.md` describe `<source>` y `make archive`. No concluir que una integración comercial o separar procesos queda automáticamente fuera de obligaciones: requiere revisar arquitectura y trabajo combinado con asesoría.

El material de `vendor/` y dependencias tiene licencias propias: se comprobó, como ejemplo, ISC de `vendor/libsodium/LICENSE`; eso **no es una auditoría exhaustiva de licencias ni un SBOM de una imagen construida**. Revisar overlay OPAM, bibliotecas OCaml, frontend y sistema base al fijar la build. No se identificó en H0 una prohibición técnica de estudiar una copia local; la compatibilidad jurídica de explotación/comercialización permanece pendiente. No se emite dictamen jurídico ni se confirma normativa chilena aplicable a un cliente concreto.

## 7. Diferencias con master 4.0.0~dev

Comparación fijada a `8888045a7650df5241a76ae75128ebde61e83904`; no usar el estado futuro de master como contrato. Se inspeccionaron diff de API y código; no se ejecutó 4.0.

| Área | 3.3.0 | Snapshot 4.0.0~dev |
|---|---|---|
| Versión API | `api_version=6` | `api_version=7` |
| Login administrativo | `login/<servicio>`, DELETE `login` | `login/admin/<servicio>`, DELETE `login/admin` |
| Login votante | Flujo web con estado | Añade contrato `login/voter` con estado como Bearer |
| Votantes | `voter_list` | Tipo `voters` |
| Boletas activas | `ballots_with_weights` | `ballots_info`; añade `ballots/<prefijo>` |
| Trustees | Preparación en `elections/U/draft/trustee(s)` | Recursos propios `trustees/...`, incluido flujo de eventos Pedersen; cambia tipo de trustee electoral |
| Mensajería | HMAC dentro de payload | Header `Authorization: Belenios-HMAC ...` |
| Tipos | `src/web/api/serializable.atd`, ATD | Migración a `src/web/api/types.ml` y otra representación/serializadores |
| Ruta obsoleta de borrador | API.md aún lista `draft/election`, sin despacho encontrado | Eliminada del documento |

No extrapolar ejemplos recientes de login/voto, tipos o SDKs a la PoC 3.3.0. La comparación completa de `doc/API.md` puede reproducirse con el comando de §1.

## 8. Plan de pruebas definido, NO ejecutado

Tras autorización G1, H1 debe fijar dependencias, probar aislamiento/loopback/correo fake y restauración. H2 usa dos elecciones independientes de **10 unidades sintéticas cada una**, igual papeleta homomórfica con dos opciones, peso 1 y al menos dos perfiles de autoridad. Generar identidades `unidad01`…`unidad10` y correos `votante01@ejemplo.test`…; comprobar aceptación real del dominio por flujo email/fake. Todas las claves/capacidades serán nuevas y de laboratorio, fuera de Git.

Para un primer resultado de referencia se propone una selección obligatoria entre A/B, sin modelar blanco/nulo. Diez votos iniciales: A=6, B=4. `unidad01` cambia A→B: en R1 el resultado esperado es A=5, B=5, con 10 boletas activas; en R2 el cambio se rechaza y queda A=6, B=4. Ejecutar el cambio mediante navegador y, como caso adicional, nueva boleta válida por API/modo avanzado con autenticación completa, recalculando el oracle de conteo antes de cada caso. Separar pruebas de fallo que puedan cambiar el resultado en elecciones auxiliares sintéticas. Si se añade blanco, configurar semántica explícita; una boleta criptográficamente inválida rechazada no es «voto nulo» contabilizado.

| ID | Procedimiento y criterio de aceptación | Estado H0 |
|---|---|---|
| BEL-01 | Build del commit fijado, digest/dependencias, loopback, cero SMTP externo, arranque y parada reproducibles; medir recursos | Receta inspeccionada; sin build |
| BEL-02 | Crear cada elección, cargar 10 unidades, fijar huellas de padrón/preguntas, completar validación y comprobar cierre inicial/apertura explícita | Tipos/rutas inspeccionados |
| BEL-03 | Operador y servidor de credenciales separados; comprobar certificado, entrega/reenvío fake sin alta duplicada y límites; documentar dominios de confianza | Protocolo inspeccionado |
| BEL-04 | Completar ceremonia 2 de 3; escrutar con 2, repetir ausencia de cada uno en fixtures nuevos; con 1 no publicar resultado; contar también clave server | Soporte de código/test upstream leído |
| BEL-05 | Emitir con UI oficial, conservar trackers sin vínculos en reporte; demostrar inclusión y concordancia con 10 boletas activas | Pendiente |
| BEL-06 | Instancia A permite reemplazar A→B, tracker anterior fuera de vista activa; archivo conserva historia; resultado 5/5 | Pendiente |
| BEL-07 | Instancia B rechaza segundo sufragio válido en confirmación backend tanto desde UI como envío API; diferenciar `DuplicateBallot` y `RevoteNotAllowed`; resultado 6/4 | Rama de rechazo inspeccionada |
| BEL-08 | Dos representantes ficticios de una unidad; padrón conserva una identidad/credencial; según R2 no aparece segundo voto activo; resolución de representante externa | Diseño de ensayo |
| BEL-09 | Reconstruir/copiar `.bel` público íntegro; en entorno separado ejecutar verificador 3.3.0, sin secretos/token A; comparar cifras con oracle aprobado | Comando y descarga inspeccionados |
| BEL-10 | En copia pública alterar payload real o firma/prueba sin actualizar hash referenciado; verificar fallo o registrar alcance exacto. Nunca alterar original | Diseño de ensayo |
| BEL-11 | Ejecutar rutas de contrato, vistas por rol, variantes JSON, estados, If-Match correcto/obsoleto, token ausente/ajeno/caducado, 400/401/403/404/405/409/412 y mantenimiento controlado | Matriz de código, cero HTTP funcional |
| BEL-12 | Doble submit, refresh, cierre navegador, sesión vencida, sin correo, credencial incorrecta, cierre/fecha de gracia, caída tras confirmación y restauración; trackers confirmados sobreviven | Diseño de ensayo |
| BEL-13 | Revisar entradas/egress DNS/SMTP/HTTP, cookies, logs y artefactos: datos solo sintéticos; cero secretos/padrón o vínculos identidad–tracker publicados | H0 solo fuentes públicas; flujo pendiente |
| BEL-14 | Derivar participación 10/10 y prototipo de acta desde resultado verificado; quórum/reglas definidos aparte; registrar incidentes/hash/verificador/firma | H4 posterior |
| BEL-15 | Confirmar factibilidad OTP/OIDC y límites de claims; ejecución OIDC opcional posterior con IdP local y cuentas ficticias | Revisión estática |

### Verificación externa prevista

Comandos **para H2**, en shell POSIX del verificador separado, con un único `.bel` por directorio. Debe haberse construido el `belenios-tool` fijado; no se ejecutaron aquí:

```sh
# URL base termina en /: archive pull de 3.3.0 concatena literalmente "api/...".
belenios-tool archive pull --url http://127.0.0.1:8001/ --uuid "$UUID" > "$UUID.bel"
belenios-tool election verify --dir /path/to/election
```

Si el verificador está en otra máquina/VM, su loopback no es el servidor: copiar allí el archivo público previamente descargado, o aprobar un canal aislado que permita leerlo sin publicar la demo. En Windows PowerShell 5.1 no redirigir stdout nativo binario con `>` para transportar el archivo; usar shell POSIX o copia binaria y cotejar SHA-256. Registrar versión/hash del binario, hash del `.bel`, cabeza final fijada en `Tallied`, exit code, stdout/stderr sanitizado y duración.

El comando de verificación procede de [doc/tool.md][S21]. El éxito de `election verify` sobre una elección abierta/incompleta no prueba escrutinio: exigir estado final, evento/objeto de resultado y concordancia con el oracle. Tampoco prueba elegibilidad jurídica, padrón correcto o ausencia de supresión de una cola de eventos. El ensayo negativo debe incluir (a) cambio de objeto referenciado detectado; (b) una copia truncada a un prefijo válido puede seguir siendo un archivo coherente incompleto: contrastar cabeza final anclada/monitor y resultado para detectar esa regresión. No presentar coherencia criptográfica como garantía de actualidad frente a un servidor malicioso.

Para cada caso conservar comando, entorno, entrada sintética identificada por hash, expectativa, observación real, error, resultado y vínculo de evidencia. El informe público no contiene semilla, privadas, capabilities, correo fake completo, ZIP confidencial ni spool. Un fallo o resultado desconocido se registra y resuelve antes de repetir mutaciones.

## 9. Decisión H0 y pendientes

| Pregunta | Conclusión permitida por la evidencia |
|---|---|
| ¿Autohospedaje sin servidor público? | Hay fuentes/receta y configuración local. Operación aislada, egress y restauración **no demostrados** |
| ¿Revoto y primer voto? | Soporte estático para revoto y `<deny-revote/>` global. Validación funcional UI/API y regla familiar **pendientes** |
| ¿Integración verificable con TheoGen? | API 6 y verificador identificados, con divergencias documentales. Elección íntegra, adaptador, actas y aptitud jurídica **no demostrados** |

**Recomendación H0: GO documental condicionado para presentar G1.** No se detectó una carencia estática que obligue a modificar criptografía para ensayar los dos escenarios. Este GO no aprueba la PoC, no acredita build reproducible ni equivale al GO final BEL-01…15. Si la imagen/dependencias no pueden fijarse, el flujo independiente falla o el verificador no acepta la elección, registrar NO-GO del hito correspondiente, sin avanzar a adaptador.

Antes de autorizar G1 el responsable debe decidir alcance/responsables, presupuesto y entorno; aceptar el uso de demo debug exclusivamente aislada o aprobar otra build; designar operador/servidor de credenciales, tres custodias y auditor; aprobar casos y custodia/destrucción. Quedan pendientes validación confiable de firma/procedencia, dependencias/digests, revisión AGPL para el uso previsto y política R1/R2/representación familiar con asesoría. Sprint 2 y cualquier integración/despliegue conservan sus propios gates.

**Evidencia ejecutada en H0:** consulta de rama/tag con conector GitHub; fetch/worktree documental; clonación solo de fuentes; resolución local de tag/commit; lecturas de código y hashes; diff frente al snapshot master; validación de alcance/Markdown/enlaces locales y manifiesto. Entorno: Windows, PowerShell 5.1, Git 2.55.0.windows.5, Python 3.11.7. El manifiesto registra los resultados exactos de las comprobaciones estáticas; no cuenta BEL-01…15 como aprobadas.

**Incidencias:** `git fetch` inicial fue denegado al escribir `.git/FETCH_HEAD`; tras autorización de acceso se completó. `agente.md` remoto devolvió 404 y se siguió la instrucción local del usuario. Se detectaron divergencias upstream: ruta ATD inexistente en API.md, `draft/election` sin dispatcher y apertura automática descrita por web.md frente a Closed en código. Se tratan como puntos explícitos de BEL-11, no como funcionalidades probadas. Durante el cierre, una comparación de hashes detectó cambios adicionales ajenos en el workspace original (diff modificado y nuevos `backend/tests/prepare_s2_migration_data.py`, `backend/tests/test_s2_migration_postgres.py`); no se afirma igualdad de todo ese árbol entre mediciones. H0 no escribió sus archivos de trabajo ni restauró/incluyó cambios de Sprint 2: esta PR solo propone documentación H0/corrección de ADR y su comprobador estático, sin fusión automática.

## 10. Fuentes fijadas

Los enlaces siguientes usan commit, no master. Los hashes de archivos se conservan en el manifiesto adjunto. Las páginas generales [FAQ](https://www.belenios.org/faq.html) y [setup](https://www.belenios.org/setup.html), consultadas el 28/10/2026, sirven de contexto; no sustituyen el código fijado y presentan instrucciones históricas sobre contraseñas/credenciales.

[S1]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/INSTALL.md
[S2]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/contrib/docker/demo.Dockerfile
[S3]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/contrib/docker/gitlab-ci.Dockerfile
[S4]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/opam-bootstrap.sh
[S5]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/demo/ocsigenserver.conf.in
[S6]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/demo/run-server.sh
[S7]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/tests/sendmail_fake_to_static.sh
[S8]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/doc/API.md
[S9]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/api_eliom.ml
[S10]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/api_drafts.ml
[S11]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/api_elections.ml
[S12]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/api/serializable.atd
[S13]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/api/common.ml
[S14]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/lib/core/serializable.atd
[S15]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/api_generic.ml
[S16]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_config.ml
[S17]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_main.ml
[S18]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_persist.ml
[S19]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/site_voter.ml
[S20]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/public_archive.ml
[S21]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/doc/tool.md
[S22]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/tool/tool_archive_pull.ml
[S23]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/clients/election/common.ml
[S24]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/filesystem/election_ops.ml
[S25]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/lib/core/common_types.ml
[S26]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/doc/cred.md
[S27]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/doc/auth.md
[S28]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_auth_oidc.ml
[S29]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/tests/tool/demo-threshold.sh
[S30]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/README.md
[S31]: https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/COPYING
