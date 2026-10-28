# H4 — Compatibilidad funcional y decisiones institucionales

Fecha de ejecución: 2026-10-28. G1 aprobado; continuación solicitada por el titular después de H3. ADR-001 **PROPUESTO**. Se ejecuta el ajuste técnico de laboratorio; la aprobación de motor, representación y política R1/R2 corresponde a G2.

## Unidad familiar demostrada

Se creó otra elección, `CvnVFmybmHMb19`, en la instancia con `<deny-revote/>`. El registro privado contiene diez apoderados ficticios en ocho unidades: dos familias tienen dos apoderados con correos distintos. La selección de representante es explícita, con referencia de decisión ficticia; no se infiere parentesco de RUT, apellido, dirección o correo.

`adapter/family_registry.py` impide congelar sin representante seleccionado, cambiarlo tras el congelamiento o obtener otra identidad para el apoderado alternativo. También rechaza asociar a la misma persona a dos unidades. No sustituye la acreditación ni resolución institucional: una discrepancia bloquea la preparación hasta registrar una decisión externa.

Solo ocho alias aleatorios por elección se transfieren a Belenios. La relación familia/personas/representante/alias queda en `.runtime/private/h4/family-registry.json`, fuera del motor y de Git. La autoridad CLI sin red generó exactamente ocho credenciales, cotejadas con los ocho votantes del API. No se crearon diez credenciales para diez personas. El correo de los alias es ficticio y termina en el sumidero local: **no se implementó distribución real a representantes ni recuperación/reemisión**.

Ocho votos fueron aceptados por la interfaz original; otro sufragio con el mismo derecho fue rechazado por backend con `RevoteNotAllowed`. Resultado **4/4**, ocho boletas activas, participación **8/8 = 100 %**. La exclusión del apoderado alternativo se comprobó en el registro privado; el rechazo de revoto se comprobó en Belenios con el único canal de la unidad. No se simula haber autenticado a dos apoderados reales ni autorizado compartir una credencial.

Se escrutó con custodias externas simuladas 2/3 más componente servidor. `belenios-tool` verificó el archivo en contenedor sin red, de solo lectura, con exit 0 y resultado presente. El anclaje sigue siendo local y no firmado por un tercero.

Evidencia: [elección y verificaciones](evidencias/h4-resultados.json), [navegador](evidencias/h4-navegador.json), [archivo público](evidencias/h4-publico/CvnVFmybmHMb19.bel).

## Autenticación e interoperabilidad

El flujo demostrado es la autenticación por código/email original de 3.3.0, correo ficticio y credencial privada separada. TheoGen no recibe la boleta ni su selección. Para una futura integración deben resolverse la entrega a la persona acreditada, su recuperación y la separación de dominios administrativos.

OIDC fue inspeccionado en el commit fijado, **no ejecutado**. `doc/auth.md` distingue `<auth>` para administradores y `<auth-export>` para votantes. `web_auth_oidc.ml` descubre `/.well-known/openid-configuration`, usa autorización por código y callback `/auth/oidc`, scopes `openid profile email`, intercambio servidor a servidor y `userinfo`. El login usa `email` si existe y `sub` en otro caso. No se presume equivalencia de claims Google/Microsoft con elegibilidad ni con los alias familiares. Cambios de correo, `email_verified`, emisor/tenant, vinculación estable y configuración TLS requieren prueba con IdP local antes de cualquier servicio real. No se crearon clientes OAuth ni cuentas personales.

Fuentes fijadas: [autenticación](https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/doc/auth.md), [OIDC](https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_auth_oidc.ml), [email](https://github.com/glondu/belenios/blob/337887bd1862c7cd057080b530fd80941bfc3c69/src/web/server/common/web_auth_email.ml).

R1 y R2 requieren **dos procesos/configuraciones de servidor**, no un campo por elección. Comparten imagen, pero tienen volúmenes y redes separados. H2 demostró R1 (último voto) y R2 (rechazo backend); H4 añadió la unidad familiar R2. R3 supervisado y transferencia posterior de representante no están implementados ni aprobados.

## Acta técnica, esquema y reglas sin inventar

`adapter/technical_record.py` vuelve a verificar archivo/anclaje antes de generar el esquema `theogen-experimental-record/v1` y su plantilla Markdown. [JSON](evidencias/h4-acta.json), [acta renderizable](evidencias/h4-acta.md), [cuatro comprobaciones](evidencias/h4-acta-pruebas.json).

El prototipo separa personas (10) de unidades (8), incluye conteos, participación, incidentes, huella del padrón exportado, archivo/evento/resultado, versión y verificador, autoridades y firmas pendientes. Rechaza un anclaje distinto y un denominador familiar contradictorio. La huella corresponde al padrón seudónimo exportado, **no acredita la aprobación jurídica del registro privado**.

La papeleta exige una selección A/B. Blanco/nulo figuran como `modeled=false, value=null`, no como ceros escrutados. El empate 4/4 no genera ganador ni cargo. Quórum, estatutos, representación, firmas y auditor humano independiente siguen pendientes. Este documento técnico no constituye acta jurídica, firma electrónica ni evaluación de legalidad.

## Privacidad y límites observados

Durante el ensayo se observaron 423 solicitudes del navegador, todas a `127.0.0.1`; ninguna intentó otro origen. Las urnas siguen en redes Docker internas. Se cotejó el script de correo vivo con el sumidero local, permiso `600` y rechazo de `/static/mail.txt` en ambas instancias. [Cinco comprobaciones y metadatos acotados de seis logs](evidencias/h4-privacidad.json).

Solo se publican indicadores agregados de logs, nunca su contenido. **Las muestras completas de `access.log` de ambas urnas contienen el marcador de correo sintético `@ejemplo.test`**; no se presenta la configuración debug como libre de datos identificadores. No se observó el patrón literal `?state=`/`&state=`/`?token=`/`&token=` en esas muestras, lo cual no descarta otros formatos, cuerpos o datos correlacionables. IP, hora, autenticación y trackers también pueden correlacionarse. El operador del host puede leer el correo y la correspondencia privada. Minimizar/retener/expurgar estos logs exige diseño y prueba antes de usar personas reales. No se hizo captura de paquetes DNS/SMTP del host ni se certifica ausencia de terceros para todos sus procesos. Las cookies observadas al final de los contextos no equivalen a una auditoría de cookies de autenticación; el laboratorio HTTP tampoco acredita TLS o flags productivos.

La fuente AGPL y el código correspondiente deben conservarse y ofrecerse conforme a la licencia; distribución/servicio, cambios, avisos y dependencias requieren revisión jurídica. La separación de contenedores no sustituye operadores independientes ni una política de retención/expurgo probada para logs, correo, credenciales y respaldos.

## Ajuste chileno: revisión de fuentes y decisiones pendientes

El [Decreto 565, artículo 4](https://www.bcn.cl/leychile/Navegar/imprimir?idNorma=14275&idVersion=1996-01-19) contempla una persona representante por familia para votaciones en Asamblea General. Esto orienta el caso sintético, **sin extender automáticamente esa regla a toda entidad o elección remota**. Deben verificarse personalidad jurídica, eventual Ley 19.418, estatutos, convocatoria, quórum, modalidad remota, impugnaciones y firmas de cada organización.

La [BCN informa la vigencia prevista de Ley 21.719 para 01-12-2026](https://www.bcn.cl/balance-legislativo/detalle/ficha_LEY_21719_2024-12-13). En consulta del 28-10-2026, el [Senado registra el boletín 18.623-07 en tramitación](https://tramitacion.senado.cl/appsenado/index.php?ac=boletin_x_fecha&boletin=18623-07&mo=tramitacion), y una [sesión de Hacienda del 27-10-2026](https://tramitacion.senado.cl/appsenado/index.php?ac=sesiones_celebradas&ano=2026&comi_nombre=de+Hacienda&desde=0&fecha=27%2F10%2F2026&hasta=0&idcomision=188&idpunto=nada&idsesion=23164&inicio=10%3A46&legi=0&listado=2&lugar=&mo=comisiones&termino=&tipo=3) informa aprobación particular y paso a Sala. Eso no acredita una modificación publicada. Revalidar texto y vigencia al aprobar el piloto; no fijar retención ni afirmar una prórroga consumada a partir de una noticia o proyecto.

Algunas aperturas directas de LeyChile devolvieron la pantalla de carga y Senado 403; se utilizó el texto indexado de las fuentes primarias y se conserva esta limitación. No se emitió dictamen jurídico ni se declaró cumplimiento normativo.

## Modelo breve de amenazas

| Amenaza | Control demostrado o previsto | Riesgo residual / pendiente |
|---|---|---|
| Administrador malicioso | Fuentes/imagen fijadas, archivo verificable, anclaje final | Root del host controla todos los procesos; monitor/anclaje firmados por tercero pendientes |
| Generador de credenciales comprometido | CLI externo sin red; solo públicas a urna | Puede conocer privadas; protocolo operator/server y operador realmente independiente pendientes |
| Trustees coludidos | Umbral 2/3 y rechazo de publicación con un aporte en H2 | Colusión suficiente junto al componente servidor; custodias humanas/hosts independientes pendientes |
| Dispositivo votante malicioso | Boleta/archivo verificados por herramienta externa | No prueba intención del elector ni seguridad del dispositivo/JS servido |
| Coacción remota | R1 permite sustitución; R2 rechaza nuevos sufragios | Ninguna política certifica resistencia a coacción; aceptación institucional pendiente |
| Fuga de correo | Sumidero fuera del webroot, permiso 600 | Host/backup puede revelar OTP y metadatos; entrega real y expurgo pendientes |
| Fallo o rollback de servidor | Reinicio conserva votos en H2; restore sintético en H1 | Restore posterior a votos, RPO/RTO y cotejo independiente de pérdidas pendientes |
| Correlación identidad/boleta | Alias por elección, correspondencia privada, acta agregada | IP/tiempo/logs/credenciales/trackers y operador común permiten correlación |

## Recursos medidos y costo por presupuestar

[Tres muestras](evidencias/h4-recursos.json): urnas aproximadamente 29 MiB cada una y 0,14–0,21 % CPU; proxies aproximadamente 110–113 MiB cada uno. Son muestras de baja carga, no prueba de concurrencia ni capacidad máxima. Límites configurados: 768 MiB/2 CPU por urna y 128 MiB por proxy. La imagen compartida ocupa 2.323.381.000 bytes; los volúmenes completos con todas las elecciones sintéticas midieron 1.022.652 y 1.162.478 bytes aparentes. No sumar dos veces la imagen para estimar dos instancias ni equiparar bytes aparentes con disco físico/backups.

Preparación automatizada H4: 13,969 s; cierre, escrutinio y verificación: 9,422 s. Son tiempos de máquina de este ensayo, excluyen deliberación, distribución, preparación humana, asistencia y custodia. H1 registró compilación 111,8 s, exportación/carga 110 s y extracción inicial de base 467,3 s en pasos separados; no son una duración total de instalación.

Para R1/R2 se mantienen dos procesos, dos volúmenes y dos configuraciones de respaldo/actualización. Falta presupuestar dominios administrativos independientes, correo real, monitoreo, retención, disponibilidad, soporte, horas de autoridades/auditor y mantenimiento. No hay cotización ni cifra CLP. Tres muestras pequeñas no dimensionan una elección institucional.

## Reproducción y decisión

Desde `poc/belenios-3.3.0/`, con H1–H3 y dependencias de pruebas disponibles:

```powershell
python tests/setup_h4.py
cd tests
node vote_ui.mjs --family
cd ..
python tests/tally_h4.py
python tests/check_h4_record.py
python tests/check_h4_privacy.py
python tests/measure_h4.py
```

Los pasos con mutaciones rechazan intentos/estados previos inciertos; no recrear ni repetir sufragios automáticamente. Las comprobaciones del acta y privacidad son de lectura sobre elecciones completas y se pueden repetir; las marcas temporales/muestras pueden variar.

**GO para conservar/revisar el ajuste técnico de laboratorio. NO-GO para elección oficial o integración productiva.** BEL-08 y prototipo de BEL-14 tienen evidencia adicional; no se certifica el conjunto H4 por faltar auditoría humana independiente, entrega real, captura completa de egress, reglas jurídicas y operación endurecida. La siguiente decisión revisable es G2: motor, unidad electoral, R1/R2 y custodios, acompañada de la evidencia y pendientes; no se acepta el ADR de forma implícita.
