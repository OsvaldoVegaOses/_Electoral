# Sprint 3 — Cierre técnico de integración a main

**Fecha:** 2026-10-29, Chile. **Resultado:** código integrado y probado localmente en `main`; candidato de CI alternativa aprobado en Azure. **GitHub Actions:** bloqueado por facturación, sin pasos ejecutados. **Aceptación operacional M1/M2:** pendiente de sus demás criterios externos.

## Integración realizada

El [PR #10](https://github.com/OsvaldoVegaOses/_Electoral/pull/10) fue fusionado por autorización expresa del titular. Commit de integración: `f2f87dc918f4c25aff28165a3876519f03aa35f3`; candidato: `dc34864e908a4ce5663658cf0e210bd7d645423c`. Ambos comparten el árbol Git `8139c3ef9507f0e0ac1b1a3a2448180be1fc5d0c`.

Se reunió Sprint 1, S2-A/B/C/D/E, el paquete HMAC completo y PoC/ADR. Los PR 1–9 se cerraron como sustituidos por #10; las ramas, conversaciones y árboles originales se conservaron. Los heads de 3–9 son ancestros del merge; 1–2 contienen documentación preservada o sustituida por la versión vigente del ADR.

Se corrigió la frase que aún decía que Sprint 2 y ADR no tenían validación conjunta. La consolidación y su comprobación ya ocurrieron; el bloqueo externo de CI y la activación del piloto son estados separados.

## Pruebas sobre main

Ejecución en un checkout limpio, con bases nuevas y contenedores sintéticos etiquetados. La [evidencia sanitizada](../Sprint_3/evidencias/main-validacion.json) registra el SHA probado, hashes de artefactos y árboles de código. El commit documental posterior conserva esos árboles; no se atribuye el resultado a código diferente.

| Control | Resultado | Alcance |
|---|---|---|
| Backend completo | **213 aprobados, 0 fallos, 0 omitidos** | PostgreSQL 16/Redis 7 reales locales |
| Migraciones | Un head; instalación vacía/Sprint 1 y actualización S2-B/ADR ya aplicados | Votos, derechos consumidos, instantáneas, huellas y operaciones UNKNOWN conservados; downgrade destructivo rechazado con rollback |
| Auditoría/Redis | Concurrencia y fallos aprobados | Dos procesos, 100 eventos, rol no propietario, UPDATE/DELETE rechazados y HTTP 503 durante caída Redis |
| Backup/restore | **13 tablas iguales** | Incluye gestión Belenios y entregas pendientes no vacías; no restaura una urna real |
| Arranque de release | **5 escenarios aprobados** | API productiva sin DDL; migración explícita separada; auto-migración productiva bloqueada |
| E2E HTTP/Chromium/PostgreSQL | **9 aprobados** | Login/logout, cookies, CSRF, ámbito, padrón con Belenios apagado, voto familiar, rechazo del otro integrante, cierre, 50% y PDF |
| UI Belenios | **5 aprobados** | API simulada; no certifica proveedor real |
| Frontend | Lint/build aprobados | Conserva advertencias de lint/MUI y tamaño del bundle |
| Dependencias | Sin vulnerabilidades conocidas al escanear; npm ci: 0 | Resultado fechado del entorno/dependencias; no garantía permanente |
| Secretos | Contenido publicable e historial del candidato aprobados | 30 commits escaneados; excepciones por ruta y valores públicos/ficticios exactos; control negativo detectado |
| Compose/Nginx | Configuración aprobada | No acredita TLS/DNS ni despliegue del destino |

## CI externa: Azure aprobado y bloqueo GitHub comprobado

El [run del PR](https://github.com/OsvaldoVegaOses/_Electoral/actions/runs/40895742039) y el [run de main](https://github.com/OsvaldoVegaOses/_Electoral/actions/runs/40896304217) finalizaron antes de ejecutar pasos. La anotación de GitHub dice: “The job was not started because your account is locked due to a billing issue.”

El titular autorizó usar Azure CLI como alternativa. ACR Tasks ejecutó el candidato `9905708cb466f46fc141e53b75ecb370d4dd3063` en `ch1b`, finalizado `Succeeded` el 2026-10-29 a las 19:06:50 UTC. Los diez controles pasaron: 213 backend sin fallos/omisiones, 9 E2E reales, 5 contratos UI con dobles, lint/build, auditorías Python/npm, secretos del contenido e historial y Compose/Nginx. La [evidencia sanitizada Azure](../Sprint_3/evidencias/azure-candidato.json) registra SHA, resultados y el digest OCI de los informes retenidos.

Se corrigió `wheel 0.45.1` de la imagen base, actualizándolo a `0.48.0`; el escaneo completo posterior quedó sin vulnerabilidades conocidas. Se conservan obligatorios todos los controles. El [procedimiento reproducible](../Sprint_3/ci-azure.md) usa un host temporal y servicios sintéticos propios, sin desplegar el producto ni modificar aplicaciones existentes.

Cada merge requiere repetir Azure sobre el SHA exacto resultante y publicar un estado separado del commit con su evidencia. El run `ch1b` acredita únicamente su candidato; el estado Azure del SHA de main identifica la validación posterior. GitHub Actions conserva su bloqueo real hasta que su administrador resuelva facturación; un resultado Azure no cambia ni falsifica ese estado. La revisión independiente permanece abierta.

## Pendientes separados del cierre técnico

- Aceptación completa M1: comprobar el estado Azure del SHA final, revisión independiente, custodia externa de checkpoints y controles de entrega/retención que corresponden al mandato. Las operaciones peligrosas siguen bloqueadas; no se reduce tácitamente el alcance de Sprint 2.
- M2/G3: servidor seleccionado, despliegue/verificador validado, identidad y entrega, autoridad/custodios/auditor independientes, reglas institucionales y ensayo/restore del destino. El verificador externo permanece como prototipo pendiente de validación operacional.
- G4: aceptación propia de la primera elección vinculante. La correlación histórica `Vote.voter_id`/`candidate_id` permanece y no se afirma secreto del voto MVP.

**Belenios sigue apagado por defecto.** No se enviaron correos, incorporaron participantes reales, alteraron urnas previas ni desplegó un piloto. Los comandos de reproducción y la separación entre migrador y aplicación constan en [integración a main](../Sprint_3/integracion-main.md).
