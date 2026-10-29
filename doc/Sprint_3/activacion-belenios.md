# Requisitos para activar Belenios y operar TheoGen Electoral

**Fecha:** 2026-10-28, Chile.

**Estado:** diagnóstico de código, evidencia disponible y requisitos propuestos; activación pendiente.

**Plan de ejecución:** [Sprint 3](../sprint3.md).

## 1. Determinación

TheoGen ya tiene una integración Belenios ejecutada en laboratorio. Para dejarla activa fuera del equipo de desarrollo hace falta completar el adaptador, la identidad/entrega, los recorridos de la aplicación y la operación del servidor. Configurar una variable no habilita esos contratos: el cliente rechaza otros entornos/destinos y el verificador depende de redes y contenedores del PoC.

El objetivo recomendado es una versión integrada seguida de un piloto no vinculante. El salto a elección vinculante exige los requisitos institucionales y G4 del ADR, además de que el software funcione.

## 2. Qué está implementado y qué demuestra la evidencia

El diagnóstico original se basó en `d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9` ([PR #9](https://github.com/OsvaldoVegaOses/_Electoral/pull/9)). **Actualización 2026-10-29:** los cambios posteriores de Sprint 2 y ADR ya se reunieron en `feat/sprint3-integration` y tienen validación conjunta local. La integración a `main`, sus pruebas y el cierre técnico se registran en el [estado vigente](estado-implementacion.md); la activación del piloto conserva sus requisitos propios. Las tablas siguientes mantienen el corte diagnóstico original y deben leerse junto a esa actualización.

| Capacidad | Estado observado | Límite |
|---|---|---|
| Crear y vincular borrador | Implementado; alias aleatorios, una unidad por representante, configuración cotejada | Solo borrador sin votos/derechos MVP; máximo actual de 100 representantes por petición |
| Gestionar estados | Intención persistida, reserva condicional, `If-Match`, bloqueo `UNKNOWN` y reconciliación | Operación manual de laboratorio; no calendario automático ni servicio productivo |
| Votar | Recorrido documentado con interfaz nativa Belenios, credenciales externas y R2 | Datos ficticios; no autenticación/entrega a electores reales |
| Autoridades | Ceremonia 2/3 ensayada con procesos separados | Mismo host/operador; no independencia institucional demostrada |
| Verificar resultado | Archivo público y resultado contrastados con huellas; verificador sin red | Ejecutor y anclaje del mismo laboratorio; dependencias Docker fijas |
| Consultar evidencia | JSON agregado, personas/unidades y huellas | Expediente experimental; firmas, quórum y acta jurídica pendientes |
| Evitar mezcla de motores | Rutas MVP bloqueadas para una elección vinculada | Dashboard mixto y actas MVP devuelven 409; falta alternativa completa Belenios |
| Pruebas | Backend/PG/UI y proveedor real documentados en ADR; S2 tiene reporte local separado de 165 casos | No constituyen un E2E del producto integrado ni un run CI final verde |

Fuentes de estas capacidades: [informe ADR](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/motor/implementacion_adr001.md), [evidencia de recorrido](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/motor/evidencias/adr001-live.json) y [evidencia PostgreSQL](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/motor/evidencias/adr001-postgres.json). Se inspeccionaron; no se repitieron esos ensayos al redactar el diagnóstico.

## 3. Bloqueos concretos encontrados en el código

Las rutas de la tabla pertenecen al SHA ADR salvo indicación contraria. Los cambios propuestos son trabajo pendiente.

| Área | Implementación actual | Cambio necesario |
|---|---|---|
| Habilitación | `backend/app/belenios/client.py::require_enabled` exige `BELENIOS_MODE=laboratory` y `ENVIRONMENT=development` | Capacidad explícita para el entorno aprobado, con validación de configuración y habilitación por institución |
| Destino API | `BeleniosClient` solo acepta `http://127.0.0.1:18001`/`18002` | Destinos internos administrados, autenticados y con TLS verificado; mantener protección SSRF y prohibición de redirects arbitrarios |
| Comprobación R1/R2 | `check()` usa `docker inspect/exec` y nombres del PoC para comprobar versión y flag | Contrato operativo que pruebe versión y política efectiva; no inferir el flag desde una API que no lo publica |
| Verificador | `verification.py::public_archive` usa imagen, ruta de herramienta y redes `theogen-belenios33-poc_*` | Ejecutor aislado con interfaz limitada, compatible con la versión desplegada y ajeno al privilegio del API web |
| Enlaces navegador | `routers/belenios.py::status` publica enlaces solo para los loopback fijados | URL pública HTTPS independiente del endpoint de control; sin capacidades administrativas en enlaces |
| Identidad | `service.py::prepare` genera `unit-…@ejemplo.test` y selecciona autenticación `Configured/email` | Alias con entrega real o identidad externa compatible; comprobar la correspondencia exacta del representante con la identidad admitida |
| Credenciales MVP | En el árbol S2, alta/importación de padrón y apertura llaman `require_credential_delivery()`; bloquea producción | Separar padrón y emisión por motor. Un padrón Belenios no debe emitir tokens MVP ni quitar la protección global |
| Entrega | En S2 existe `app/brevo.py` con transporte y tests; `credentials.py` sigue bloqueando producción | Integrar ciclo persistido de provisión/entrega/conciliación. Brevo no activa Belenios ni sustituye una autoridad de credenciales |
| Papeleta | Una pregunta homomórfica, selección obligatoria, sin blanco/nulo modelados; idioma inicial `en` | Aprobar este alcance o ampliar todo el contrato con verificación y UI; completar español |
| Aplicación | Panel de laboratorio, dashboard combinado bloqueado y expediente JSON | Recorridos por rol, dashboard, resultados y actas/PDF propios de Belenios |
| Contenedor API | `backend/Dockerfile` no instala CLI Docker; la verificación actual ejecuta Docker desde el host | Empaquetar el servicio verificador separado; no solucionar montando el socket del host dentro del API |
| Stack productivo | Plantilla con frontend/backend/PostgreSQL; sin despliegue completo de Redis, Belenios y verificador | Manifiestos, persistencia, redes, secretos, healthchecks, backup y configuración de todos los componentes |
| Release | Dos ramas de esquema al reunir S2 y ADR; CI bloqueada por cuenta GitHub | Migraciones reconciliadas, workflow completo y ejecución del SHA final |

Fuentes principales de inspección: [cliente](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/backend/app/belenios/client.py), [servicio](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/backend/app/belenios/service.py), [verificador](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/backend/app/belenios/verification.py), [router](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/backend/app/routers/belenios.py), [panel](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/frontend/src/components/BeleniosPanel.jsx) y [plantilla de despliegue](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/templates/docker-compose.prod.yml).

## 4. Arquitectura de destino propuesta

La propuesta describe componentes y fronteras. No selecciona un proveedor cloud ni presupone cuentas, dominios o capacidad contratada.

| Componente | Función y acceso | Requisito de operación |
|---|---|---|
| Frontend TheoGen + API | Gestión, padrón, representantes, estados y evidencia agregada; roles institucionales | HTTPS, cookies/CSRF, CORS fijado, secretos persistentes y controles de ámbito |
| PostgreSQL | Datos de gestión, vínculos e intenciones; sin boletas nuevas Belenios en `Vote` | Acceso privado, rol de aplicación limitado, migrador separado, backup y restore probado |
| Redis | Protección de abuso compartida entre instancias | Acceso privado y autenticado según topología; política de caída segura sin fallback silencioso |
| Belenios | Interfaz nativa de voto y estado electoral | Build revisada sin modo debug/dummy, almacenamiento persistente, acceso público HTTPS y administración restringida |
| Política R1/R2 | Variante de revoto aprobada | Una instancia si solo se admite una política; instancias aisladas si se sirven ambas, porque el control probado es por proceso |
| Ejecutor de verificación | Recibe referencias públicas permitidas, verifica archivo y produce evidencia limitada | Identidad propia, imagen compatible fijada, límites de recursos, sin privadas ni privilegios del API; verificación sin red |
| Autoridad de credenciales | Generación, entrega y recuperación de privadas | Persona/entorno independiente de TheoGen y de la administración de urna; procedimiento y custodia aprobados |
| Custodios de descifrado | Ceremonia y aportes para escrutinio | Propuesta 2 de 3, personas y dispositivos separados; copias protegidas bajo su control |
| Monitor/auditor y custodia | Comprobar continuidad, cabeza final, archivo y resultado | Dominio administrativo independiente, referencias autenticadas y recibos verificables |
| Identidad y entrega | Autenticar al representante y hacerle llegar lo necesario para votar | Método probado, destinatarios controlados, soporte de fallos y recuperación |
| DNS/TLS, secretos, backup y alertas | Acceso, continuidad y operación diaria | Titularidad/renovación, acceso mínimo, respaldos externos cifrados y responsables de guardia |

La separación de dominios administrativos significa que una misma cuenta con privilegios sobre todo no pueda modificar urna, monitor y evidencia sin detección. Contenedores o subdominios distintos bajo el mismo control no bastan para demostrar esa independencia.

Para el primer piloto se propone mantener el voto en la interfaz nativa y completar la gestión en TheoGen. Esto reduce el trabajo de integrar una cabina nueva y conserva la separación ya ensayada. La interfaz no debe mostrar formularios de selección que envíen boletas o preferencias al backend TheoGen.

## 5. Identidad y credenciales: decisión imprescindible

Belenios distingue credencial electoral y autenticación del votante. La documentación de operación separa sus mecanismos y las autoridades que los gestionan; se debe probar la combinación elegida para nuestro padrón. [Configuración oficial](https://www.belenios.org/setup.html).

**Precaución de versión:** las notas de 3.3.0 eliminan las contraseñas estáticas generadas por elección para votantes. No reutilizar instrucciones antiguas que recomienden esa modalidad; contrastar configuración y API de la versión desplegada. [Notas 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/RELEASE_NOTES.md).

| Alternativa a evaluar | Qué requiere | Condición de elección |
|---|---|---|
| Autenticación por correo con alias operativos | Dominio/relay o mecanismo de entrega compatible, correspondencia controlada y envío de códigos al representante | Demostrar entrega y recuperación sin exponer privadas a TheoGen ni habilitar otro miembro de la misma unidad; evaluar el poder del operador del relay |
| OIDC u otro protocolo soportado | Proveedor, cliente/callbacks y mapeo de identidad compatible con el padrón/alias | Probar el login real, el identificador usado por Belenios y los errores de cuenta/cambio de representante. No asumir que acepta automáticamente la sesión TheoGen |

OIDC está documentado en 3.3.0; no es obligatorio para este proyecto. Si se elige modo restringido, comprobar sus restricciones: la configuración documentada limita autenticación y autoridades, de modo que no debe combinarse con cualquier alternativa por suposición. [Protocolos](https://github.com/glondu/belenios/blob/3.3.0/doc/auth.md), [modo restringido](https://github.com/glondu/belenios/blob/3.3.0/doc/web.md).

La decisión debe registrar dónde se conserva cada correspondencia, quién conoce la identidad real y quién puede entregar o recuperar una credencial. Se proponen estas fronteras:

- TheoGen: padrón institucional, representante elegido y alias; acceso restringido y retención aprobada.
- Autoridad independiente: relación necesaria para entrega de la credencial privada, respaldo y reenvío autorizado.
- Belenios: identidad/alias admitido y material público/boletas del protocolo; el contacto real solo si el diseño aprobado lo necesita y lo informa.
- Custodios: sus claves privadas; TheoGen no tiene endpoints para recibirlas.

Con autoridad externa, la herramienta oficial distingue archivos privados y públicos; permite conservar el privado protegido para reenviar la misma credencial. La recuperación de nuestro producto debe respetar esa identidad y la política R1/R2, sin crear una segunda unidad ni prometer revocaciones que el contrato ensayado no ofrece. [Herramienta 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/doc/tool.md).

## 6. Qué significa que la aplicación funcione correctamente

| Usuario/área | Flujo mínimo exigido | Criterio verificable |
|---|---|---|
| Administrador | Institución, usuarios, roles, elección y motor | Aislamiento entre colegios y asignaciones válidas; ninguna elevación implícita |
| Comisión | Padrón, familias, representante, papeleta y calendario | Congelamiento trazable; exactamente una unidad por persona/familia según regla aprobada |
| Representante | Invitación/entrega, autenticación, acceso a cabina, voto y comprobación | Puede completar el recorrido en móvil; la selección no pasa por TheoGen; rechazo del no habilitado/alternativo |
| Autoridad/custodios | Preparación, entrega y ceremonia | Públicas cotejadas; privadas externas; umbral y recuperación ensayados |
| Operador | Abrir/cerrar, observar estado y conciliar incidentes | Estado remoto confirmado; `UNKNOWN` bloquea mutaciones; ausencia de reapertura indebida |
| Auditor | Obtener archivo y anclaje, verificar y detectar alteración | Verificación completa con resultado final y origen autenticado desde otro dominio administrativo |
| Comisión/producto | Dashboard, resultados, participación y acta/PDF | Personas y unidades diferenciadas; cifras de Belenios verificadas, sin ceros inventados ni consultas a `Vote` para esa elección |
| Soporte | Fallos de entrega, pérdida de credencial, caída y elección suspendida | Procedimientos con responsables, límites y registros sin secretos |
| Operación | Reinicio, backup, restore y actualización | Votos reconocidos y estado de operaciones conservados; sin duplicación ni rollback electoral silencioso |

La papeleta actual no contempla blanco/nulo ni una elección con varias preguntas o selección múltiple. Antes del piloto se debe aprobar explícitamente la modalidad soportada o desarrollar esas variantes, incluidos verificador, actas y pruebas. Los totales ausentes no se transforman en ceros ni se infieren ganadores o quórum sin reglas aprobadas.

El calendario requiere una decisión operativa: apertura/cierre manual con responsables o programación confirmada por el proveedor. La aplicación debe gestionar zona horaria, incidentes y divergencias. El estado local no puede afirmar que la urna está cerrada sin cotejo remoto.

## 7. Infraestructura, servicios y personas por confirmar

| Recurso/decisión | Información necesaria | Quién lo aporta | Verificación antes de activación |
|---|---|---|---|
| Hosting | Recursos existentes, ubicación, acceso, almacenamiento y conectividad | Titular + operación | Inventario, capacidad y topología probados; no confundir Docker Desktop con alojamiento del piloto |
| Dominio y DNS | Nombres públicos de app/urna y acceso a su zona | Titular/administrador DNS | Resolución, TLS válido, renovación y URLs/callbacks correctos |
| Correo o identidad | Método elegido, proveedor/cuenta, remitente/dominio y cuotas | Operación + responsable de identidad | Entrega o login end-to-end con identidades controladas; rebotes/errores y recuperación |
| Secretos | Sesión, HMAC aplicables, API Belenios, correo/IdP y backup | Operación + autoridades correspondientes | Almacenamiento protegido, permisos, recuperación y rotación ensayados; privadas fuera de TheoGen |
| Runners GitHub | Cuenta habilitada y permisos sobre checks/artefactos | Administrador GitHub | Run verde sobre el SHA candidato; el bloqueo observado es de facturación |
| Custodia externa | Personas, repositorio/destino, acceso y conservación | Auditor + custodio | Recibo y descarga/verificación independiente de ambas clases de anclaje |
| Volumen y continuidad | Personas/unidades, concurrencia, elecciones simultáneas, ventana y SLO | Producto + operación | Ensayo de carga y objetivos de latencia/error/RPO/RTO aceptados |
| Comisión y autoridades | Nombres, roles, disponibilidad y sustituciones | Institución + titular | Simulacro completo, dispositivos y custodias separados |
| Reglas institucionales | R1/R2, familia/representante, papeleta, fechas, quórum/desempate y actas | Institución + asesoría | Aprobación G2 aplicable; documentos y límites del piloto |
| Operación y presupuesto | Guardia, soporte, monitor, backup, revisión de licencias/seguridad y costes | Titular + operación | Responsables y partidas cotizadas con base en capacidad; sin precios estimados sin fuente |

No es necesario contratar un servidor por cada fila: algunas funciones pueden compartir infraestructura con aislamiento apropiado. La autoridad, los custodios y el auditor sí requieren una independencia efectiva conforme al modelo aprobado; alojar todo bajo una cuenta administrativa única no la acredita. La viabilidad de recursos existentes aún debe inventariarse.

## 8. Seguridad, continuidad y mantenimiento

1. **Versión:** conservar 3.3.0 y su commit como referencia del PoC, no como afirmación de que sea la última versión o la indicada automáticamente para producción. Revisar mantenimiento, avisos y compatibilidad antes del despliegue; cualquier actualización exige volver a probar API, archivo, autoridades y verificador.
2. **Build:** sustituir la receta debug/dummy de laboratorio por una build revisada, con fuentes/base/dependencias identificadas, inventario y escaneo. Mantener herramienta y archivos electorales compatibles. La documentación advierte que el modo dummy es para demostración. [Servidor 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/doc/web.md).
3. **Red:** HTTPS público, API/BD/Redis privados, destinos salientes permitidos, administración restringida y confianza de proxy explícita. Comprobar cookies/CSRF/cabeceras desde el navegador real.
4. **Logs:** el PoC documentó marcadores de correo ficticio en `access.log`. Definir minimización/redacción y probar access/security/app logs, trazas, spool y artefactos sin registrar códigos, privadas o correspondencias innecesarias.
5. **Persistencia:** respaldar PostgreSQL y el estado persistente Belenios con un procedimiento coordinado; inventariar cuentas/configuración/secretos aplicables. El spool contiene material sensible y tiene custodia/retención propia. [Persistencia del servidor](https://github.com/glondu/belenios/blob/3.3.0/doc/web.md).
6. **Restore:** recuperar en entorno separado, contrastar archivos/cabezas y todas las boletas reconocidas con el monitor independiente, además de mappings e intenciones. No reabrir desde una copia anterior a votos aceptados ni repetir operaciones remotas al restaurar la BD local.
7. **Observabilidad:** salud/dependencias, desfase de estado, errores de envío, capacidad, latencia y fallos de verificación; alarmas con responsable. Un `/health` HTTP 200 no prueba que pueda escrutarse una elección.
8. **Datos y licencias:** política aprobada para padrón, correspondencias, logs, respaldos y expediente; legal hold y procedimientos de incidente. Revisar obligaciones AGPL y dependencias según el despliegue; no presentar este documento como dictamen jurídico.

## 9. Gates de activación y evidencia de aceptación

| Gate | Requisitos | Evidencia exigida | Situación inicial |
|---|---|---|---|
| **Integración a main — M1** | Alcance resuelto, S2 reconciliado, migraciones seguras, pruebas y revisión | SHA candidato, CI verde, matriz de cierre y PR contra `main`; comprobación posterior a fusión | PENDIENTE |
| **Ensayo técnico del destino** | Stack fuera del PoC, identidad/entrega, autoridades y recorridos completos | Nueva elección sintética, E2E con usuarios de prueba, carga, fallos, TLS y restore | PENDIENTE |
| **G2 institucional** | Motor A ya autorizado técnicamente; completar política y reglas de cada institución | Aprobación escrita de unidad/representante, R1/R2, papeleta, calendario, responsables y riesgos | PARCIAL |
| **G3 — M2** | M1 y ensayo aceptados, revisión externa y operación preparada | Aceptación del piloto no vinculante, participantes/alcance y versión/entorno concretos | PENDIENTE |
| **G4** | Dictamen y aceptación institucional, actas/reglas, auditoría, simulacro y continuidad | Aprobación formal de elección vinculante según ADR | PENDIENTE; no cubierta por un simple encendido |

Para el ensayo completo: crear padrón/representantes, preparar urna, verificar públicas/autoridades, entregar/autenticar, votar desde la cabina nativa, comprobar R1/R2, cerrar, aportar umbral, obtener archivo/anclaje y verificar, presentar dashboard/acta y restaurar una copia sin pérdidas. Probar también usuario incorrecto, representante alternativo, respuesta perdida, umbral insuficiente, archivo antiguo/alterado y proveedor caído.

El informe debe separar evidencia de código, tests con dobles, servicios reales locales, servicios del destino y revisión independiente. Una caída de GitHub no autoriza afirmar que CI pasó; un piloto técnico correcto no acredita por sí solo legalidad o resistencia frente a todos los actores.

## 10. Decisión recomendada y siguiente ejecución

Preparar primero M1 y la arquitectura del piloto. Elegir después el destino, método de autenticación/entrega, custodios y reglas para ejecutar el ensayo y solicitar G3 sobre un resultado revisable. Mantener las privadas fuera de TheoGen y la cabina nativa de Belenios.

Las decisiones que más condicionan esfuerzo y coste son: si se soportan ambas políticas R1/R2, qué papeletas exige la institución, cómo llega la autenticación al alias, si continúa emisión MVP y qué volumen/disponibilidad se necesitan. Se registran como entradas de S3-00/03/05/06/07, no como supuestos ya resueltos.

La primera implementación debe preservar las barreras actuales mientras agrega sus reemplazos probados. Tras la aceptación, la activación será un cambio controlado de capacidad y despliegue; no un cambio del servidor a modo `development`.

## 11. Fuentes y alcance de la consulta

Se inspeccionaron código y evidencias locales de la rama ADR y el árbol S2, el PR #9, comparación remota con `main` y la anotación de CI. No se consultaron inventarios de cuentas cloud, DNS o correo del titular, ni se probó un despliegue externo durante esta preparación.

Las fuentes upstream consultadas están fijadas a 3.3.0 cuando describen su contrato. La página general de instalación puede describir otros periodos; ante diferencias prevalecen las notas y el código de la versión elegida, comprobados por ejecución. No se afirma aquí que la web general determine la última versión disponible.

- [Instalación y separación de roles](https://www.belenios.org/setup.html).
- [Notas de versión 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/RELEASE_NOTES.md).
- [Autenticación 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/doc/auth.md).
- [Servidor, persistencia y modo restringido 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/doc/web.md).
- [Herramienta de credenciales y verificación 3.3.0](https://github.com/glondu/belenios/blob/3.3.0/doc/tool.md).
- [ADR del SHA inspeccionado](https://github.com/OsvaldoVegaOses/_Electoral/blob/d9a6def287ee2bb18aeb4dfc2ece18dcd24300a9/doc/adr/001-motor-de-votacion.md).

**Resultado:** integración de laboratorio disponible; activación del piloto y funcionamiento integral del producto pendientes de los cambios y evidencias descritos. El detalle de tareas, responsables y aceptación está en el Sprint 3.
