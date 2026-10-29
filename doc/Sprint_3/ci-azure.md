# CI mediante Azure CLI y ACR Tasks

**Alcance autorizado:** ejecutar la CI alternativa en Azure sin depender de los runners GitHub bloqueados por facturación. No habilita el piloto ni modifica los servicios TheoGen desplegados.

Se usa el registro existente `theogenongtcacr`, grupo `new`, mediante una QuickRun temporal. No se crea una VM persistente ni un task con webhook, y no se cambian roles, redes, secretos o aplicaciones existentes. Las pruebas usan PostgreSQL/Redis propios del ejecutor temporal; cada contenedor tiene nombre único y una etiqueta con el SHA de origen.

## Preparación y ejecución

El runner incluye Python 3.11, Node 22, Docker/Compose y Chromium. La tarea construye el runner, ejecuta diez controles obligatorios y conserva evidencia en `electoral-ci/evidence:<run-id>` únicamente si todos pasan. Las imágenes de CI tienen un espacio propio; no se publican imágenes del producto.

Las herramientas Python se fijan en `pip 26.2.2`, `setuptools 84.2.1` y `wheel 0.48.0`. La imagen Python original incluye `wheel 0.45.1`, afectado por [CVE-2026-24049](https://github.com/advisories/GHSA-8rrh-rw8j-w5fx); se actualiza antes de instalar dependencias y auditar el entorno completo. El auditor imprime paquete, versión, aviso y versiones corregidas cuando falla, sin omitir el control.

```powershell
python scripts/prepare_azure_ci.py --output .runtime/azure-ci-context-NUEVO
az acr run --registry theogenongtcacr --resource-group new --file acr-task.yaml --set expected_sha=SHA_COMPLETO --timeout 3600 --no-wait .runtime/azure-ci-context-NUEVO
az acr task list-runs --registry theogenongtcacr --resource-group new --top 5
az acr task show-run --registry theogenongtcacr --resource-group new --run-id RUN_ID
az acr task logs --registry theogenongtcacr --resource-group new --run-id RUN_ID
```

Si la CLI Windows falla al mostrar Unicode, descargar los logs por la API oficial sin imprimir ni guardar el enlace SAS temporal:

```powershell
.\scripts\download_azure_ci_logs.ps1 -Registry theogenongtcacr -ResourceGroup new -RunId RUN_ID -Output .runtime/azure-ci-RUN_ID.log
```

El empaquetador exige un árbol limpio y un commit exacto. Solo envía un Git bundle, el Dockerfile, la tarea y un manifiesto público: no incluye `.env`, claves, bases, venv, node_modules ni resultados locales. Los procesos de prueba reciben únicamente configuración y credenciales sintéticas.

El socket Docker se usa solo en el contenedor CI del host temporal ACR; no se añade al API ni a una plantilla de despliegue. Las pruebas del entrypoint transportan su fixture por stdin para funcionar también con un daemon remoto, manteniendo los mismos cinco casos y expectativas.

## Evidencia y criterio de aprobación

Controles: backend/migraciones/concurrencia/restore sin skips, lint/build, E2E con HTTP/PostgreSQL, UI Belenios con dobles, auditorías Python/npm, secretos del contenido e historial, Compose y Nginx. Los fallos detienen la tarea y no se convierten en éxitos ni en omisiones.

Los logs completos permanecen en Azure y en `.runtime` al descargarlos. El colector `scripts/collect_azure_ci.py` acepta una sola salida sanitizada con SHA/run-id coincidentes y diez etapas aprobadas. La aprobación también exige que Azure marque el run `Succeeded` y que exista el manifiesto de evidencia retenida. Se conservan JUnit, auditorías, resumen y SHA-256 de artefactos; no se exportan fixtures privados ni capturas/trazas del recorrido real.

Una ejecución Azure aprobada es CI Azure, no GitHub Actions verde ni desbloqueo de la facturación GitHub. Se puede publicar un estado separado del commit que enlace la evidencia Azure. Los gates de revisión independiente, custodia, entrega e infraestructura del piloto conservan su alcance.

Referencias oficiales: [ejecución de tareas por CLI](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tasks-multi-step) y [contrato YAML/variables](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tasks-reference-yaml).
