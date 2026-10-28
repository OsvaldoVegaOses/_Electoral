# SPIKE-BEL-01 — Cierre de la ejecución autorizada G1

Fecha: 2026-10-28. ADR-001 permanece **PROPUESTO**. Alcance ejecutado: H1, recorrido electoral de H2, adaptador experimental H3 y ajuste técnico H4, siempre en laboratorio local con datos ficticios.

| Hito | Resultado sustentado | Evidencia |
|---|---|---|
| H1 | GO de laboratorio: build y dos instancias, 29 comprobaciones | [Instalación](02-instalacion-aislada.md), [JSON](evidencias/h1-resultados.json) |
| H2 | Dos elecciones escrutadas/verificadas: 5/5 y 6/4; revoto UI/API, 2/3 y tamper test; siete fallos adicionales | [Protocolo](03-protocolos-y-matriz-pruebas.md), [resultados](04-resultados-verificacion.md), [JSON](evidencias/h2-resultados.json) |
| H3 | Prototipo funcional, ocho comprobaciones; exporta solo después de verificar/anclar | [Contrato](05-adaptador-experimental.md), [JSON](evidencias/h3-resultados.json) |
| H4 | Elección familiar: 10 personas/8 unidades, resultado 4/4, archivo verificado; acta técnica y mediciones | [Compatibilidad, amenazas, fuentes y límites](05-compatibilidad-theogen-chile.md), [JSON](evidencias/h4-resultados.json) |
| G2–G4 | Pendientes; H4 conserva brechas de auditoría humana, operación y aprobación jurídica | No se declara GO global de PoC, uso vinculante ni integración productiva |

## Respuestas alcanzadas

1. **Autohospedaje:** Belenios se construyó desde el commit fijado y funcionó sin su servidor público. Las urnas estuvieron en redes internas sin ruta por defecto y con correo fake privado. Los proxies de ingreso y el host no están certificados como entornos sin conectividad; no se realizó una captura exhaustiva de todo egress.
2. **Revoto y familia:** el laboratorio demostró R1 y rechazo backend R2 en procesos distintos, tanto desde UI original como mediante envío por API con autenticación. H4 probó un único representante/alias/credencial por unidad sintética, sin identidad adicional para apoderados alternativos. Sigue pendiente aprobar jurídicamente la política y representación familiar. No se inventó criptografía ni se cambió la de upstream.
3. **Interoperabilidad:** existe un contrato API 6 ejecutado y un adaptador local que crea borradores sintéticos y produce evidencia estructurada de resultados verificados. No hay integración con los votos, tablas o autenticación existentes de TheoGen.

## Decisión y límites

**GO para conservar y revisar el prototipo aislado. NO-GO para uso oficial, despliegue o integración productiva en este estado.** La independencia real de autoridades/auditor, los límites pendientes de H4, evaluación jurídica, firma de anclajes/actas, privacidad de metadatos, endurecimiento y los gates posteriores siguen pendientes.

No se presenta como probado el protocolo nuevo de servidor/operador de credenciales, timeout natural de 900 s, entrega a electores sin correo, todas las ausencias de trustees, OIDC o protección frente a coacción/dispositivos/administrador malicioso. Un verificador puede aceptar un prefijo válido sin resultado: el requisito de resultado completo y anclaje final es obligatorio.

Las fuentes/receta y las pruebas están en un worktree y rama aislados de Sprint 2. No se modificaron el motor, su autenticación o infraestructura productiva. Los archivos públicos de las elecciones sintéticas se publican con hashes; material privado, correo, respaldos y journals quedan ignorados. La limpieza y sus límites de borrado físico se describen en el README del laboratorio.
