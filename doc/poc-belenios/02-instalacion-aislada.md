# H1 — Instalación aislada y evidencia de arranque

Fecha: 2026-10-28. G1 autorizado por el usuario en esta sesión; ADR-001 continúa PROPUESTO. **Resultado H1: GO de laboratorio** para ejecutar H2, sin integración productiva.

## Procedimiento y entorno observado

Se siguió el [README reproducible](../../poc/belenios-3.3.0/README.md). Fuente `337887bd1862c7cd057080b530fd80941bfc3c69`, tag anotado `2f0c5eb950d964baeea95f81ff6db7c418020ba5`. Imagen base oficial `glondu/beleniosbase@sha256:3d57d508592aa94124473052e0beefcb6c06408fcbb1ded99febd6e70c4e7b62`. El archivo tar sin conversión de líneas tiene SHA-256 `8a696a8ae0331ceb998d979970d82d5c86fbedd66aa837507c0d6b042b126244`.

Windows + Docker Desktop 4.54.0, Engine 29.1.2 Linux/amd64 sobre WSL2, Compose 2.40.3. Docker informó 16 CPU y 3.77 GB RAM disponibles para la VM. No se cambió su asignación ni se limpiaron recursos ajenos. Se inició Docker Desktop, que estaba detenido.

El paso de compilación exitoso duró 111.8 s; exportación/carga de esa primera imagen compilada, 110.0 s. La extracción inicial de la capa grande de la base tardó 467.3 s, aparte de la descarga. Estos son tiempos observados de pasos concretos, no una promesa de duración total ni costo. Las capas del proxy se reconstruyeron luego usando la compilación cacheada.

El [informe JSON](evidencias/h1-resultados.json) conserva imagen final, tamaño, muestra de CPU/RAM y duración de pruebas. El código compilado declara Belenios 3.3.0/API 6. Las dependencias OCaml vienen en la base fijada; npm resolvió 123 paquetes y emitió una advertencia de severidad baja. No se hizo `npm audit fix`, actualización de upstream ni auditoría completa de vulnerabilidades. La dependencia npm aún requiere congelamiento exhaustivo para prometer una build determinista; la receta ejecutada y sus límites quedan explícitos.

## Aislamiento medido

Dos urnas, volúmenes distintos, flags de revoto distintos, redes Docker internas separadas sin ruta IPv4 por defecto. Publicación real exclusivamente en `127.0.0.1:18001` y `127.0.0.1:18002` mediante proxies de destino fijo; las urnas no publican puertos directamente. Se verificó `Internal=true`, configuración de bindings real y fallo de una sonda a TEST-NET-2 (198.51.100.1). No se transmitieron datos electorales en esa sonda.

La red de ingreso de cada proxy tiene conectividad del host Docker; la ausencia de ruta se demuestra para las urnas, **no para todos los procesos del equipo**. El proxy solo dirige HTTP a su urna estática y rechaza CONNECT/destino absoluto. No se afirma haber realizado captura exhaustiva de DNS/HTTP o análisis de todos los terceros: eso forma parte de BEL-13/H4.

Correo fake fuera de `static`, sin SMTP externo. `/static/mail.txt` devuelve 400 en esta versión/configuración y se confirmó ausencia del archivo público: no se interpreta ese 400 como un mensaje vacío. Se conservan capturas/logs sanitizados; no se publican mensajes ni estados con capacidades.

## Pruebas ejecutadas

Comando: `python scripts/check_h1.py`, desde `poc/belenios-3.3.0/`. Resultado final: **29 comprobaciones satisfactorias**, detalle en JSON. Entrada ficticia: una marca de persistencia de laboratorio; no se creó un padrón real ni se utilizó una cuenta personal.

- Configuración/versión/API de ambas urnas, acceso administrativo sin token rechazado, ruta inexistente rechazada y correo no publicado.
- Flags de revoto opuestos, bindings de proxies en loopback y ausencia de publicación/ruta por defecto de las urnas.
- Reinicio de la urna B con conservación de la marca sintética.
- Indisponibilidad al detener B: 502 o timeout acotado del cliente mientras el proxy no encuentra upstream.
- Backup completo del volumen B, restauración en un volumen nuevo, misma marca y arranque de un servidor desde la copia con API 6.
- Eliminación del contenedor/volumen de restauración H1 y reanudación de la urna B original. Se conserva el backup local ignorado; eliminar un volumen no prueba borrado físico.

## Errores reproducidos y correcciones locales

1. Git global `core.autocrlf=true` convirtió los scripts del primer tar a CRLF, provocando `execve ... No such file or directory`. `prepare.py` fuerza `core.autocrlf=false` al archivar el commit. Se verificó shebang LF antes de recompilar.
2. La base contiene `wget`, no `curl`; el healthcheck inicial falló por ejecutable inexistente. Se sustituyó por `wget`, sin tocar autenticación.
3. Docker Desktop no activó bindings efectivos para una urna conectada únicamente a red interna. Se conservó esa red y se añadieron proxies locales de destino fijo; no se habilitó salida en las urnas.
4. El cliente HTTP Node observó respuesta 200 completa de 1101 bytes seguida por `0\r\n\r\n`, con `HPE_INVALID_CONSTANT`. El proxy acepta solo ese terminador adicional exacto después de respuesta completa; no usa un parser HTTP inseguro general. Respuestas incompletas/otros errores siguen fallando. Es una limitación de compatibilidad a revisar antes de un diseño productivo.
5. `docker system df` informó un snapshot local inexistente durante el inventario. La descarga y build terminaron; no se reparó ni limpió almacenamiento Docker ajeno.
6. El controlador de navegador conectado devolvió «No browser is available». No se declara validación visual en H1.

## Siguiente hito

H2: dos elecciones sintéticas de diez unidades, credenciales operadas fuera de la urna, ceremonia de trustees, sufragio/revoto y archivo público verificado en un proceso separado. Este GO de H1 no acredita ninguna de esas propiedades ni autoriza uso vinculante. H3 solo comienza tras la verificación íntegra de H2.
