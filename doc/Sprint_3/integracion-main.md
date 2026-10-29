# Integración a main — alcance técnico y procedimiento

**Autorización vigente, 2026-10-29:** el titular indicó «debemos pasar a main, probar y cerrar». Se autoriza publicar y fusionar el candidato conjunto con Belenios apagado, probar el resultado en `main` y cerrar los PR sustituidos. Esta instrucción no activa un piloto, un envío de credenciales ni una elección vinculante.

El candidato reúne el historial de Sprint 1, S2-A/B y PoC/ADR, además de S2-C/D/E y el paquete completo HMAC de `unit_key`. La decisión de publicar la integración completa sustituye el diferimiento documental anterior del paquete, sin reducir sus criterios de prueba. `Vote.voter_id` y `candidate_id` históricos permanecen; no se certifica secreto del voto MVP.

## Comprobaciones para la integración

- Instalación vacía y actualización desde Sprint 1, S2-B aplicado y ADR aplicado. Los casos incluyen Borrador/Abierta/Cerrada/Finalizada, voto reconocido, derecho consumido, instantánea/huella congeladas y operación remota `UNKNOWN`; el downgrade con datos debe rechazarse sin mutación parcial.
- Backend con PostgreSQL 16/Redis 7, concurrencia, rollback y rol de auditoría no propietario; restore de las 13 tablas comparadas con datos de gestión no vacíos.
- E2E con HTTP/Chromium/PostgreSQL reales y cinco contratos de UI Belenios con API simulada. No repetir las urnas históricas del PoC.
- Lint/build, configuración Compose/Nginx, auditoría de dependencias y escaneo de secretos del contenido e historial. Las advertencias de frontend se conservan como deuda técnica.
- Commit del candidato, PR contra `main`, comprobación de CI, integración por autorización del titular y repetición sobre el SHA resultante. Un problema externo de runners se informa como tal; no se convierte en CI verde ni en aprobación operacional.

Los PR documentales 1 y 2 tienen commits distintos a los de la integración: el contenido de Sprint 2 coincide salvo el salto final; el ADR fue sustituido por la versión que registra la autorización de implementación. Los PR 3–9 contienen historia incorporada al candidato. Cerrar los originales como sustituidos conserva sus conversaciones y commits; no se eliminan ramas ni worktrees.

## Migración separada de las réplicas

El contenedor API arranca mediante `entrypoint.sh serve` sin ejecutar Alembic por defecto. `RUN_MIGRATIONS_ON_STARTUP=true` solo se admite en desarrollo/test; en producción/staging bloquea el arranque. `entrypoint.sh migrate` ejecuta únicamente la migración y termina.

La plantilla productiva usa dos identidades: `DATABASE_URL` de aplicación limitada y `MIGRATION_DATABASE_URL` del job de release. `.env.backend` contiene solo configuración del API; nunca la URL/clave del migrador ni la del propietario PostgreSQL. `.env.migration` es exclusiva del job. La plantilla no inyecta el archivo completo `.env` en esos contenedores.

Una vez revisados el entorno, los roles y el respaldo, el operador ejecuta una sola migración coordinada, con las réplicas fuera de servicio o bajo la estrategia de actualización aprobada:

```sh
docker compose -f docker-compose.prod.yml --profile release run --rm migrate
docker compose -f docker-compose.prod.yml up -d backend frontend
```

El rol migrador posee el esquema; el rol de aplicación recibe solo permisos de uso, DML y secuencias necesarios, sin propiedad, superusuario, creación de roles o de bases. La provisión de esas identidades en el destino sigue pendiente de elegir servidor; los ejemplos no crean usuarios ni compran infraestructura.

## Qué se cierra y qué sigue pendiente

El cierre técnico comprende integración y comprobaciones locales del código en `main`. La aceptación completa M1 conserva CI del SHA final, revisión independiente, custodia externa, entrega real y decisiones de retención que correspondan al mandato. Si alguna falta, se mantiene identificada y abierta.

M2 y G3 permanecen pendientes: despliegue/verificador del piloto, DNS/TLS, identidad y entrega, autoridad/custodios/auditor y ceremonia independientes, reglas institucionales y ensayo del destino. No se envían correos ni se usan participantes reales por esta integración. G4 requiere su propia aceptación.

La ejecución y las referencias finales se registran en [estado de implementación](estado-implementacion.md) y en la evidencia de la rama publicada.
