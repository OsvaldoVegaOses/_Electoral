# Instancia Azure para prueba de producción

Fecha: 2026-10-29. Despliegue solicitado por el titular para pruebas con administrador, sin elección vinculante.

URL: https://electoral-production-trial.purplesea-6f0b36f2.eastus2.azurecontainerapps.io/login

## Recursos y código

Grupo `new`, Container App `electoral-production-trial` en el entorno existente `theogen-env`, con contenedores frontend, backend y Redis propios. Una réplica mínima y máxima. No se modificaron las aplicaciones TheoGen existentes.

PostgreSQL 16 nuevo: `electoral-prodtest-pg-261029`, base `electoral_trial`, westus3, General Purpose `Standard_D2ds_v5`, 32 GiB, respaldo de siete días, sin HA. Los tamaños Burstable fueron rechazados por Azure; sus aprovisionamientos fallidos entraron en eliminación automática. Estos recursos permanecen activos para la prueba y generan consumo Azure.

Código construido: `49efa0844c7a94a7be78e12dcea1dfe79513ae2d`; build ACR `ch1g`, revisión `electoral-production-trial--49efa08`.

| Imagen | Digest |
|---|---|
| `theogenongtcacr.azurecr.io/electoral-trial/backend:49efa08` | `sha256:d01e9a8489860c3ba94f0077c5b580bb096ccf3ec79fb4f41b7acfbee15224e5` |
| `theogenongtcacr.azurecr.io/electoral-trial/frontend:49efa08` | `sha256:73cfb95dc69783914a791206a70f4ca750e85029c4c71e1eb6627176afd1b979` |

## Configuración y acceso

`ENVIRONMENT=production`, HTTPS obligatorio, JWT/HMAC independientes en secretos de Container Apps. Sin migraciones automáticas, seed demo, correos ni activación Belenios. Se creó explícitamente `admin@theogen.cl`, rol Administrador General, con contraseña aleatoria; su contraseña no forma parte de este documento ni de Git.

La identidad administrada `electoral-trial-runtime` tiene lectura del registro y una identidad PostgreSQL `electoral_trial_app`. Se renueva el token Entra al abrir conexiones y se verifica TLS con la cadena CA y el hostname. El rol de aplicación tiene DML, sin propiedad del esquema, superusuario, creación de bases/roles ni permiso CREATE sobre public. Las migraciones se ejecutaron separadamente con la identidad del operador.

El firewall PostgreSQL permite la salida real de la app, medida desde el contenedor: `68.220.243.198`. El metadato de salida de Azure devolvía otra dirección; se comprobó el tráfico real antes de corregir la regla. Esta IP puede cambiar con reemplazos de infraestructura: volver a medirla después de revisiones/reubicaciones. La prueba no configura NAT dedicado ni certifica continuidad productiva. Se retira la regla temporal `DeploymentOperator` tras aprovisionar.

## Evidencia

CI ACR `ch1f`, estado Succeeded, sobre el SHA de código indicado: diez controles, 213 backend sin fallos/omisiones, 9 E2E reales y 5 contratos UI con dobles, auditorías, secretos y Compose/Nginx. Los reportes se retienen en `electoral-ci/evidence:ch1f` y su resumen local en `.runtime/deploy/ci-ch1f.json`.

Prueba HTTPS desplegada: once comprobaciones aprobadas de UI/API, denegación anónima, login y rol administrador, cookies Secure/HttpOnly, sesión autenticada, lectura PostgreSQL, CSRF, logout y revocación. Chromium aprobó login, panel visible, ausencia de JWT en localStorage y logout. Se conservan los reportes y captura del panel en `.runtime/deploy/`; no contienen contraseñas ni tokens.

El administrador no abre una elección por este despliegue. La aceptación institucional, revisión independiente, custodia externa y activación Belenios mantienen sus criterios separados.

Referencia: [conexión PostgreSQL con identidad administrada](https://learn.microsoft.com/en-us/azure/postgresql/security/security-connect-with-managed-identity).
