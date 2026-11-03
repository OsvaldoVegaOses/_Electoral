# Verificador de archivos públicos Belenios

Actualización 2026-11-03: imagen corregida construida en ACR `ch1s` y desplegada en la VM del proveedor. Digest `sha256:a8a34da5893706e161db4cb3c6cffdba3009cf85e7e2c2232f68ee90acb99ce6`. El Dockerfile corrige el permiso de travesía de `/home/belenios` y comprueba la ejecución nativa como UID 10001 durante el build. El ejercicio nuevo de cinco votos pasó para las tres parejas 2/3; el worker aceptó el archivo final válido y rechazó su copia alterada. Véase [ejercicio y límites](../../doc/Sprint_3/ejercicio-belenios-03nov.md). El candidato sigue sin commit ni CI completa de su SHA final y no está habilitado en la aplicación Electoral. No constituye una auditoría humana independiente.

Los párrafos siguientes conservan el diagnóstico previo al build de ACR y no describen el estado actual de esa imagen desplegada.

La construcción local del contenedor candidato agotó su límite de 240 s. La conciliación posterior no encontró la etiqueta esperada ni contenedores en ejecución. No se repitió el intento ni se declara comprobado el empaquetado o arranque de Compose. La herramienta nativa usada en las seis pruebas anteriores pertenece a la imagen debug de laboratorio; los Dockerfiles candidatos exigen el formato release nativo `3.3.0 (3.3.0)`.

El prototipo anterior `verifier/service.py` no satisface las nuevas cabeceras requeridas por el backend. Actualizar backend y servicio como un único candidato validado; no conectar el backend nuevo al verificador antiguo.

## Contrato

`POST /verify` acepta únicamente `{"policy":"R2","uuid":"CvnVFmybmHMb19"}` con Bearer privado y TLS. R1 admite revoto; R2 lo prohíbe. Las URL de proveedor son configuración del operador, nunca entrada del cliente. No se reciben votos, claves privadas ni credenciales electorales.

El colector descarga el archivo público mediante `belenios-tool archive pull`, enlaza el UUID a la cadena Setup del archivo y publica un trabajo. Un proceso separado, sin red ni secretos, verifica el resultado final con Belenios 3.3.0, commit `337887bd1862c7cd057080b530fd80941bfc3c69`. Requiere éxito nativo y el marcador de comprobación completa; una elección sin resultado se rechaza.

La respuesta 200 contiene exactamente el archivo verificado y cabeceras `X-Belenios-Archive-SHA256`, `X-Belenios-Upstream-Commit`, `X-Belenios-Tool-Image` y `X-Belenios-Final-Result: verified`. El backend coteja estas referencias y la huella de los bytes recibidos. Las cabeceras vinculan el protocolo; no prueban quién administra el servidor.

## Preparación del operador

1. Construir el Dockerfile desde la raíz del repositorio, pasando `BELENIOS_TOOL_IMAGE` por digest inmutable. La base debe incluir Python 3 y el ejecutable nativo instalado; no usar la imagen PoC para declarar producción.
2. Conservar el digest de la imagen base y el digest de la imagen de servicio resultante. `VERIFIER_TOOL_DIGEST` y `BELENIOS_VERIFIER_IMAGE` contienen el mismo digest SHA-256 de la base nativa. `VERIFIER_SERVICE_IMAGE` referencia la imagen de servicio por digest de registro.
3. Crear fuera de Git un directorio privado de spool con `inbox` y `outbox`, ambos propiedad de UID/GID 10001 y modo 0700 en Linux. Crear un token aleatorio de al menos 32 caracteres ASCII sin espacios y archivos TLS legibles únicamente por el servicio. No montar Docker, datos privados del proveedor ni secretos SMTP en el worker.
4. Configurar las variables obligatorias de `compose.yaml`: imágenes, spool, tres rutas de secretos y `VERIFIER_PROVIDERS`, por ejemplo el mapa JSON de R1/R2 con los destinos HTTPS aprobados. No se distribuyen destinos ni secretos por defecto.
5. Validar `docker compose -f deploy/belenios-verifier/compose.yaml config --quiet`, arrancar en un host controlado y publicar el puerto local únicamente mediante un proxy HTTPS autorizado. El colector también exige TLS al escuchar fuera de loopback. Verificar `/health`, rechazo sin autenticación, archivo final válido y copia alterada rechazada.

`network_mode: none`, raíz de solo lectura, capacidades eliminadas y ausencia de secretos en el worker son límites verificables del contenedor. La identidad y custodia externa requieren evidencia adicional. El operador debe asegurar una CA confiable y DNS/red de salida que solo alcancen los proveedores autorizados.

## Límites y conciliación

Se serializan solicitudes mediante `inbox/.busy`; el archivo incluye UUID, política, identificador y hora del trabajo. No hay reintento automático. Un timeout conserva el bloqueo. Un reinicio con `.claim` sin resultado requiere revisión humana antes de otro intento.

Para conciliar: detener la entrada de solicitudes, leer `.busy`, cotejar el trabajo y su huella con el resultado correspondiente de outbox y comprobar si el worker sigue ejecutándose. Conservar la evidencia; retirar un bloqueo solo después de resolver la operación. No borrar bloqueos ni claims de un trabajo activo. Este candidato no automatiza recuperación ni retención.

Máximo 32 trabajos retenidos, archivo de 8 MiB, contenido descomprimido de 16 MiB, 20 000 entradas, salida nativa de 64 KiB, descarga de 15 s y verificación de 30 s. El colector espera hasta 35 s después de descargar. Archivos mayores o elecciones que excedan esos límites fallan de forma cerrada y requieren una revisión de capacidad. Una vez conciliados, archivar evidencia pública fuera del spool y aplicar la retención aprobada antes de alcanzar el límite.

## Evidencia y límites de validación

Las pruebas automatizadas cubren autenticación, límites, aislamiento lógico, identidad, huellas, respuestas incompatibles y operaciones pendientes. Además se ejecutó el worker con la herramienta nativa sobre tres archivos públicos previamente generados en laboratorio: los tres válidos pasaron y las tres copias alteradas fueron rechazadas. Eso no acredita un despliegue vivo, independencia institucional ni una elección nueva con custodios externos.
