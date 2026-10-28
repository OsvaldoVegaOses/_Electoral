# ADR-001 — Implementación controlada Belenios

Fecha: 2026-10-28. El titular solicitó «Implementa el ADR» después de H0–H4. Se implementó la alternativa A, Belenios 3.3.0 (`337887bd1862c7cd057080b530fd80941bfc3c69`), dentro de TheoGen. Esta autorización técnica no acredita G2 institucional, G3 o G4.

## Comportamiento entregado

El detalle de elección incorpora un panel de motor cuando `BELENIOS_MODE=laboratory` y `ENVIRONMENT=development`. Por defecto está apagado; otras combinaciones no permiten operaciones Belenios. No hay activación productiva, cuentas externas, despliegue o migración de votos.

Antes de preparar se exige un borrador sin votos ni derechos MVP, una política R1/R2 explícita, referencia de aprobación, exactamente un representante por unidad y confirmación de la papeleta soportada. Se admite una pregunta homomórfica de selección obligatoria entre dos o más opciones regulares; blancos/nulos no se modelan y se exportan como `null`, no como ceros escrutados. Las opciones institucionales MVP marcadas blanco/nulo no se transfieren en esta modalidad explícita.

Para una regla familiar, las unidades se obtienen del `familia_id` ya validado institucionalmente y normalizado; no se infieren parentescos de RUT o apellido. La comisión selecciona un representante por grupo. Para la regla personal se exige uno por persona. Registros bloqueados/incompletos o selecciones contradictorias impiden preparar.

Tres tablas nuevas conservan la vinculación, correspondencia privada representante/alias y operaciones. Cada alias es aleatorio por elección. Solo esos alias y configuración pública se envían al proveedor; RUT, nombres/contactos del padrón, familia, tokens MVP y selecciones no se transfieren. No se agregan boletas a `Vote` ni se modifica su estructura, `Voter` o `VotingEntitlement`.

Una vinculación bloquea escrituras heredadas de esa elección, apertura/voto MVP y actas/escrutinio calculados desde la tabla `Vote`. El dashboard combinado devuelve 409 si su ámbito incluye elecciones Belenios, hasta disponer de agregación entre motores; no muestra un cero MVP como resultado externo. La vinculación sigue protegiendo la elección aunque se apague la función.

## API y operación

Todas las rutas parten de `/api/elections/{id}/belenios`, requieren autenticación TheoGen y control existente de institución/elección. Una comisión sin asignación o de otra institución no puede leer ni operar. Las mutaciones usan la protección CSRF existente cuando hay cookie de sesión.

| Ruta | Comportamiento |
|---|---|
| `GET /` | Estado confirmado, política, conteos, operación pendiente y acciones permitidas; resultado solo si fue verificado |
| `POST /prepare` | Reserva local, crea borrador por API 6, carga alias y coteja padrón/configuración |
| `GET /units` | Correspondencia privada de representante/alias; sin credenciales; solo para actores autorizados |
| `POST /transition` | `ValidateElection`, `Open`, `Close`, `ComputeEncryptedTally`, `ReleaseTally` con `If-Match` y cotejo posterior |
| `POST /reconcile` | Adopta un estado coincidente tras revisión explícita de la operación exacta; no reenvía mutaciones |
| `POST /verify` | Contrasta anclajes, configuración pública, conteos y archivo; ejecuta verificador antes de persistir resultado |
| `GET /record` | Evidencia agregada experimental; 409 si falta verificación completa |

La preparación exige `request_id` UUID, `policy` R1/R2, `representative_ids`, `approval_ref`, `ballot_mode=mandatory_single_choice_no_blank_no_null` y `synthetic_laboratory=true`. No se aceptan campos extra de boletas o claves privadas.

La autoridad de credenciales y los trustees operan **fuera** de TheoGen, mediante el procedimiento nativo de Belenios. La aplicación no ofrece endpoints para subir privadas, semillas, selecciones o claves de descifrado. Antes de validar exige credenciales listas, padrón congelado coincidente y la variante real `Threshold` 2/3 con tres custodias listas. No declara que tres procesos sean tres operadores independientes.

No se escruta antes de un cierre confirmado ni se reabre desde este flujo una elección cerrada. Un cierre registra su fecha efectiva; el estado local finaliza únicamente al persistir evidencia verificada. El calendario no se transfiere a `automatic-dates`: la apertura/cierre de este ensayo son operaciones manuales, sin afirmar automatización de plazos o validación estatutaria.

## Intenciones, errores y concurrencia

La intención se confirma en BD **antes** de cada mutación remota. Una actualización condicional de estado/operación reserva un único envío. No se permite repetir un UUID de petición ni operar mientras quede una intención pendiente/desconocida. `If-Match` se obtiene del cuerpo GET exacto, SHA-256 y Base64 sin padding.

La pérdida de respuesta, error posterior o cotejo fallido conservan la operación bloqueada como `UNKNOWN`/pendiente. Si la creación devolvió UUID antes de otro fallo, se conserva inmediatamente. Una creación sin respuesta no se repite: el operador debe localizar/cotejar el borrador mediante la referencia opaca y completar su revisión externa. La reconciliación solo acepta configuración/padrón exactos o el estado esperado de la transición. No repara ni vuelve a crear por sí sola.

Los escritores de elección se serializan en PostgreSQL con el lock de la fila padre. Completado/reconciliación aplican una condición sobre el propietario de la operación: una respuesta tardía o error de una operación anterior no sobrescribe el estado siguiente. El registro de operaciones es trazabilidad operacional, **no** un ledger firmado ni custodia independiente; el defecto general de auditoría de Sprint 2 no se declara cerrado.

Los clientes deshabilitan proxies de entorno y redirects, limitan tamaño/timeout y usan únicamente los dos destinos loopback fijados. API 6 no publica el flag de revoto: el modo de laboratorio inspecciona el runtime Docker y su configuración efectiva, además de comprobar versión/API. No se infiere R2 de un botón o de un campo inexistente del API.

## Resultado verificado y expediente

El auditor aporta cabeza final, hash del objeto de resultado, SHA-256 del `.bel` y referencia del anclaje. Se exige Tallied, configuración pública coincidente con el borrador aprobado, una pregunta soportada, pesos unitarios, sumas/participación compatibles y correspondencia API/archivo.

Se usa la imagen inmutable registrada en H1, cotejando su commit. El colector obtiene solo datos públicos; otro proceso verifica con `--network none`, filesystem de lectura, capacidades retiradas y únicamente el directorio público montado. Un prefijo válido sin resultado no se acepta. El backend de laboratorio se ejecuta en el host con Docker CLI; **no se monta el socket Docker en el contenedor del API**. Este ejecutor no es una arquitectura productiva ni auditoría humana independiente.

El expediente incluye conteos por opción, personas/unidades, participación, referencias de archivo/evento/resultado, imagen/commit y estado jurídico experimental. No contiene opciones votadas por persona, privadas o correspondencias. Firmas vacías, quórum no evaluado y `independent_custody_confirmed=false` mantienen visibles los límites.

## Configuración de laboratorio

| Variable | Valor / propósito |
|---|---|
| `BELENIOS_MODE` | `off` por defecto; `laboratory` solo en desarrollo |
| `BELENIOS_R1_URL` | `http://127.0.0.1:18001` exclusivamente |
| `BELENIOS_R2_URL` | `http://127.0.0.1:18002` exclusivamente |
| `BELENIOS_R1_ADMIN_TOKEN`, `BELENIOS_R2_ADMIN_TOKEN` | Bearer administrativo suministrado fuera de Git; `SecretStr`, nunca UI/URL/errores |
| `BELENIOS_VERIFIER_IMAGE` | Identificador `sha256:…` inmutable de H1 |

El arranque de las urnas está en el [README del laboratorio](../../poc/belenios-3.3.0/README.md). La API TheoGen usa su configuración normal de base, sesión y CSRF, más esas variables; las credenciales administrativas no se entregan al frontend. `.runtime/`, bases de pruebas y resultados generados quedan ignorados.

## Evidencia ejecutada

Base de integración: merge `3162981c21c79511a837305fe3f7aeb00046d57f`, que reúne S2-B publicado (`65c164c`) y H4 publicado (`1176714`). Los 51 cambios sin commit de Sprint 2 no se incorporaron. La rama de implementación es independiente; no se fusionó main.

| Comprobación | Resultado y alcance |
|---|---|
| `pytest tests -q --tb=short --disable-warnings` | **127 passed, 8 skipped**. Cuatro omitidas son los casos PostgreSQL que se ejecutaron aparte; las otras dependencias omitidas no se consideran aprobadas |
| `pytest tests/test_belenios_integration.py` | **15 passed**: ámbito, representante, minimización, bloqueo MVP, intención duradera, reconciliación, respuesta tardía, estados y resultados negativos |
| `python tests/run_belenios_postgres.py` | **4 passed** en PostgreSQL 16.10; upgrade vacío, downgrade a S2-B y upgrade; rechazo de downgrade poblado; contenedor propio eliminado |
| `npx playwright test --config playwright.belenios.config.js` | **5 passed**, UI real con respuestas API sintéticas; no equivale a autenticar usuarios reales |
| Ensayo `smoke_belenios_local.py` + `belenios-native.mjs` | API TheoGen por ASGI TestClient con usuario sintético inyectado, BD SQLite separada y proveedor Belenios real; ceremonia externa 2/3, dos votos nativos, revoto R2 rechazado, resultado **1/1**, archivo verificado y expediente recuperable |
| `npm run build`, `npm run lint` | Satisfactorios; se mantienen advertencias preexistentes y bundle mayor de 500 kB |

Evidencia de datos: [recorrido real](evidencias/adr001-live.json), [PostgreSQL](evidencias/adr001-postgres.json). Entorno local de pruebas: Python 3.11, FastAPI 0.162.0 y SQLAlchemy 2.1.6 instalados en el venv disponible; los pins del repositorio se comprueban separadamente en CI, sin confundir ambas evidencias.

Se inspeccionaron las capturas del [panel preparado](evidencias/adr001-ui-bound.png) y [resultado agregado](evidencias/adr001-ui-result.png). Corresponden a la suite UI con respuestas sintéticas; el recorrido con proveedor real se acredita separadamente en el JSON. No contienen correos, credenciales, RUT ni correspondencias privadas.

Para repetir en un laboratorio nuevo, con urnas H1 disponibles y sin estado anterior:

```powershell
# Desde backend/, con el Python del entorno de pruebas y Docker local:
python -m pytest tests/test_belenios_integration.py -q
python tests/run_belenios_postgres.py
python tests/smoke_belenios_local.py prepare
python tests/smoke_belenios_local.py authorities
# Desde frontend/:
node e2e/belenios-native.mjs
# Desde backend/:
python tests/smoke_belenios_local.py tally
python tests/smoke_belenios_local.py export-public
# Desde frontend/:
npx playwright test --config playwright.belenios.config.js
```

Los comandos mutantes del ensayo comprueban checkpoints y se detienen ante un intento incierto. No borrar esas marcas para volver a empezar sobre la misma urna. `resume-authority-read` y `resume-open` son recuperaciones acotadas documentadas en el runner, con comprobaciones previas específicas; no reintentan una creación.

Se corrigieron tres diferencias detectadas por ejecución: capacidad de carga de credenciales en texto (runner), variante `Threshold` del borrador (integración) y placeholder `%` del trigger de auditoría para que la cadena de migraciones previa arranque en PostgreSQL. La nueva revisión tiene ID único `bel001_20261028`. No se modificaron eventos de auditoría o votos existentes. El lockfile frontend se sincronizó con Playwright ya declarado en package.json.

## Pendientes que bloquean activación real

- Cierre revisado de Sprint 2: alcance selectivo, CI, migraciones/backfills con datos legados, entrega, retención y auditoría. Estas pruebas no cierran los 51 cambios locales ni autorizan su publicación en bloque.
- Operadores/custodios y monitor en dominios administrativos independientes; firma/custodia externa de anclajes, verificación por otra persona/máquina y revisión criptográfica.
- Canal real de credenciales y recuperación/reemisión; OIDC y vinculación estable de identidad; gestión accesible de representantes y discrepancias.
- Reglas institucionales: R1/R2, unidad jurídica, calendario, blanco/nulo, quórum, desempate, expediente/firma y revisión AGPL/estatutos.
- Endurecimiento: logs con marcadores de correo en H4, captura de egress, TLS/cookies, secretos/respaldos y ejecutor de verificación sin privilegios del host API.
- Pruebas de carga, continuidad/restore posterior a votos, RPO/RTO, costes y servicio operativo.

**Resultado:** integración de gestión implementada y ensayada en modo controlado. **NO-GO productivo/institucional** hasta resolver y aprobar esos gates. La selección técnica del motor no certifica sufragio secreto frente a todos los actores, resistencia a coacción ni legalidad de una elección.
