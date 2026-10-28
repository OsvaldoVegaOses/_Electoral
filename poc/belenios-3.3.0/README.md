# Belenios 3.3.0 — laboratorio autorizado G1

Entorno sintético aislado del backend TheoGen. [Autorización](../../doc/poc-belenios/00a-autorizacion-g1.md), [H0](../../doc/poc-belenios/01-factibilidad-y-contrato.md) y [evidencia H1](../../doc/poc-belenios/02-instalacion-aislada.md).

Commit upstream: `337887bd1862c7cd057080b530fd80941bfc3c69`. Base oficial fijada por digest en `Dockerfile.poc`; compilación debug oficial, exclusivamente de laboratorio. No se modifica código criptográfico ni archivos del backend actual.

## Arranque reproducible

Requisitos: Git, Python 3.11+, Docker con contenedores Linux y Compose v2. En Windows se probó Docker Desktop 4.54.0/WSL2, Engine 29.1.2, Compose 2.40.3. Ejecutar desde este directorio:

```powershell
git -c core.autocrlf=false clone --branch 3.3.0 --depth 1 https://github.com/glondu/belenios.git .runtime/upstream
python scripts/prepare.py --source .runtime/upstream
docker build --progress=plain --build-arg SOURCE_DATE_EPOCH=1782962593 -f .runtime/build/Dockerfile.poc -t theogen-belenios-poc:3.3.0-337887bd .runtime/build
docker compose -f docker-compose.poc.yml up -d --wait --wait-timeout 60
python scripts/check_h1.py
```

En Linux los mismos comandos de Docker/Git aplican; usar `python3` si ese es el nombre de Python. Esta variante no se ejecutó en un host Linux físico. La receta upstream usa `--network host`; esta PoC utiliza bridge y proxies locales y no presume equivalencia entre ambos modos.

`prepare.py` verifica tag/commit y conserva LF en el archivo tar aun cuando Git global usa `core.autocrlf=true`. No ejecutar `make clean` sobre un repositorio ajeno. La build descarga dependencias npm y la receta upstream genera su lock; registrar su inventario. Fijar fuente y base no implica reproducibilidad binaria de todas las dependencias de red.

## Acceso y datos

| Dirección | Política |
|---|---|
| http://127.0.0.1:18001 | Revoto permitido |
| http://127.0.0.1:18002 | `<deny-revote/>` |

Cada urna escucha en su red interna sin ruta por defecto. Solo los proxies de destino fijo publican puertos en loopback. Los proxies están también en redes de ingreso y no comparten la garantía de ausencia de ruta de las urnas; no son un cortafuegos frente a un host administrador malicioso.

El administrador dummy permitido es `poc-admin`, solo en este laboratorio. El correo fake va a `/home/belenios/poc-data/private/mail.txt` dentro de cada volumen, **fuera** del árbol web. No se configura SMTP externo. Nunca copiar ese archivo, privadas, semillas, tokens o spool a Git/PR/logs. `.runtime/` contiene material privado temporal y está ignorado.

El proxy implementa una compatibilidad limitada y medida: el puente Ocsigen/Cohttp de la imagen añade `0\r\n\r\n` después de una respuesta completa con Content-Length; se acepta solo ese caso exacto. Otros errores y respuestas incompletas producen 502. No es una recomendación para producción.

## Parada y limpieza del laboratorio

```powershell
docker compose -f docker-compose.poc.yml stop
docker compose -f docker-compose.poc.yml start
```

Para eliminar las dos urnas sintéticas y sus volúmenes (pierde sus datos de laboratorio):

```powershell
docker compose -f docker-compose.poc.yml down --volumes
```

El nombre de proyecto está fijado a `theogen-belenios33-poc`. No ejecutar prune global ni borrar imágenes, redes o volúmenes de otros proyectos. El borrado lógico de Docker no acredita sobreescritura física del disco; `.runtime/` y sus respaldos tienen ciclo de vida separado.
