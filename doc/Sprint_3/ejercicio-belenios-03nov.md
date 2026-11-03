# Ejercicio criptográfico Belenios del 3 de noviembre

Corte: 2026-11-03. **Ejercicio técnico aprobado con cinco votos sintéticos y custodias simuladas.** No acredita una ceremonia con personas independientes ni el recorrido de votación por la cabina del servidor. La [evidencia sanitizada](evidencias/ejercicio-belenios-03nov.json) identifica imágenes, archivo público, comprobaciones y límites.

## Resultado comprobado

Se utilizó el script oficial de umbral del commit Belenios 3.3.0 `337887bd1862c7cd057080b530fd80941bfc3c69`, adaptando la pregunta a dos opciones y omitiendo el tramo de revoto. La nueva elección sintética `JbQwmUdAiYP6L6` registró cinco sufragios cifrados: tres para A y dos para B.

| Aportes externos simulados | Componente del servidor | Resultado observado |
|---|---|---|
| Ninguno | Presente | Escrutinio rechazado |
| Solo custodio 1, solo 2 o solo 3 | Presente | Los tres casos fueron rechazados |
| Custodios 1 y 2 | Ausente | Escrutinio rechazado |
| Custodios 1 y 2 | Presente | Resultado 3–2 y verificación nativa completa |
| Custodios 1 y 3 | Presente | Resultado 3–2 y verificación nativa completa |
| Custodios 2 y 3 | Presente | Resultado 3–2 y verificación nativa completa |

En los casos rechazados, la herramienta terminó con código 124 sin añadir un resultado al archivo. Las tres parejas permitidas terminaron con código 0 y el marcador nativo de verificación completa. El worker aceptó el archivo público final y rechazó una copia con contenido alterado. Las partes privadas se generaron en un contenedor desechable sin red ni volúmenes privados y no se exportaron. No se enviaron correos.

Archivo público: [JbQwmUdAiYP6L6.bel](https://theogen-belenios-pilot-261102.eastus2.cloudapp.azure.com/_pilot/evidence/JbQwmUdAiYP6L6.bel), 45 568 bytes, SHA-256 `53b5a9be4703cd4404590a1e0eba06f406018c5e292c2922ee561e2096aaad3f`.

## Corrección del verificador

El intento anterior quedó conciliado como `FAILED`, sin contenedores desechables ni resultados públicos. La imagen anterior arrancaba los servicios, pero el usuario `10001:10001` no podía atravesar `/home/belenios`, cuyo modo era `0700`, para ejecutar la herramienta nativa. La respuesta de salud del servicio no demostraba esa capacidad.

El Dockerfile candidato concede únicamente permiso de travesía adicional sobre ese directorio y comprueba `belenios-tool --version` como el usuario final durante la construcción. ACR `ch1s` terminó `Succeeded`; imagen corregida `theogenongtcacr.azurecr.io/electoral-belenios/verifier@sha256:a8a34da5893706e161db4cb3c6cffdba3009cf85e7e2c2232f68ee90acb99ce6`. La base nativa sigue fijada al digest `sha256:d52bc2007431615c5e6034df701f5cc559f54f928b04da2b6a8c9c5b9b4fad86`.

La sustitución se detuvo después de crear el worker por una referencia faltante al archivo de token en el script de despliegue. Una lectura independiente confirmó ese estado; una continuación específica creó únicamente el colector ausente. Los dos contenedores anteriores se conservaron detenidos. La evidencia final debe confirmar ambos servicios y la ejecución nativa con el usuario restringido. No se modificaron proveedor, urnas ni configuración de la aplicación Electoral.

Pasaron 67 pruebas focalizadas locales de contrato, servicio, guardas de release, correo del proveedor y alcance de PDF. El build de imagen y esas pruebas corresponden al candidato sin commit; no constituyen CI completa de un SHA final integrado en `main`.

## Distribución de custodias para el siguiente ensayo

Los números de la prueba identifican partes simuladas y no asignan funciones a personas. Los contactos propuestos permanecen en el registro privado; no se publican datos personales en este expediente.

| Función propuesta | Separación y evidencia pendientes |
|---|---|
| Tres custodios, umbral 2/3 | Aceptación individual, ratificación del umbral, generación de partes en equipos bajo su propio control y respaldo separado. Ningún operador debe acceder a dos partes o sus copias |
| Autoridad externa de credenciales | Aceptación de función y emisión/entrega privada fuera de TheoGen y de la cuenta compartida de operación |
| Operación técnica | Administra disponibilidad y expediente público; no recibe las partes ni las credenciales privadas de los participantes |
| Revisión independiente | Persona y entorno aún por designar; obtiene el archivo y los anclajes por su cuenta y conserva su informe |

El registro privado conserva `roles_confirmed=false`, `invitations_sent=false` y `custody_independence_verified=false`. No se enviaron invitaciones. La aceptación de funciones, el modelo de confianza y las condiciones del piloto deben resolverse antes de una ceremonia real; M1/M2/G2/G3/G4 conservan sus requisitos.

## Límites y continuación

Este ejercicio prueba herramientas criptográficas y todas las parejas del umbral propuesto bajo un único operador. No prueba independencia humana, voto mediante cabina HTTPS, autenticación de representantes, entrega externa de credenciales, política R1/R2, carga de cuarenta personas, accesibilidad ni recuperación integral.

El siguiente ensayo requiere una elección nueva en el proveedor, responsables que hayan aceptado sus funciones y dispositivos separados para la ceremonia. La aplicación Electoral conserva Belenios apagado hasta completar sus gates. Véanse [alcance del piloto](alcance-piloto-no-vinculante.md) y [configuración de secreto y custodias](configuracion-avanzada-secreto.md).
