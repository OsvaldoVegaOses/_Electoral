# H2 — Resultados y verificación externa al proceso de urna

Fecha: 2026-10-28. **Resultado: recorrido electoral funcional demostrado; GO para H3 experimental**, con los límites de la [matriz](03-protocolos-y-matriz-pruebas.md). El ADR permanece PROPUESTO.

| Elección | UUID | Unidades habilitadas | Boletas activas | Resultado A/B |
|---|---|---|---|---|
| Revoto habilitado | `FvmMAXJvurGXN9` | 10 | 10 | **5 / 5** |
| Voto único | `51jhBLBdowEGd3` | 10 | 10 | **6 / 4** |

Se emitieron inicialmente 6 selecciones A y 4 B. La primera unidad cambió A→B por UI y se ejercitó otra boleta válida B por API con autenticación completa. En A la última sustituyó a las anteriores; en B ambas tentativas se rechazaron con `RevoteNotAllowed`. Reenviar una boleta ya archivada devolvió 400 `DuplicateBallot`, que es un caso distinto del rechazo de revoto.

La API devolvió 401/estado durante prevalidación, no confirmación de voto. Los tests completaron el flujo web con OTP del sumidero local y verificaron el resultado final y la vista activa. Durante el comprobador API se detectó una comparación equivocada Base64/hexadecimal: se corrigió, y la aceptación ya realizada se reconcilió mediante el hash exacto activo y una cabeza distinta al snapshot anterior. **No se repitió ese sufragio**.

## Verificación y ensayo negativo

El colector descargó el archivo mediante API pública (`archive-header`, `last-event`, `objects/H`), sin token administrativo. Después se ejecutó, en un contenedor separado sin red y montando solo datos públicos:

```text
belenios-tool election verify --dir /audit
```

Ambos archivos finales devolvieron **exit 0**, `all checks passed`, con resultado presente. Los conteos coincidieron con el oracle aprobado. Se probó que un solo aporte externo no permitía publicar (HTTP 500 y sin evento de resultado); con dos aportes se publicaron resultados válidos. Se rechazó un aporte repetido con HTTP 409.

Se alteró un byte del resultado dentro de una copia TAR conservando su nombre/hash referenciado y estructura. El verificador devolvió **exit 124 por hash diferente** en ambas copias. También se verificó un snapshot previo al escrutinio: devolvió exit 0 pero `no result to check`. Por ello el adaptador exige estado Tallied, resultado y cabeza/archivo anclados; un mensaje genérico de comprobación satisfactoria no acredita finalización ni actualidad.

## Evidencia pública y límites

- [Datos, hashes y stdout/stderr del verificador](evidencias/h2-resultados.json).
- [Siete ensayos adicionales de fallo](evidencias/h2-fallos.json).
- [Pantalla pública A](evidencias/h2-revote-resultado.png) y [pantalla pública B](evidencias/h2-single-resultado.png), inspeccionadas: cifras y 10 boletas visibles. La configuración demo no proporciona logo, un detalle cosmético sin modificar upstream.
- Los archivos `.bel` sintéticos se conservan en `evidencias/h2-publico/`; sus rutas y SHA-256 figuran en el JSON. Se excluyen padrón, correspondencias, privadas, semillas, capabilities, spool y ZIP administrativo.

Los siete ensayos adicionales demostraron rechazo de credencial incorrecta, cero votos al cerrar navegador antes de confirmar, pérdida del estado de autenticación tras reinicio, refresh con confirmación posterior, doble submit rechazado y `ElectionClosed` sin agregar otra boleta. El API acepta una identidad sin dirección en un borrador; no se probó entrega real de OTP a una persona sin correo. Tampoco se esperó el timeout natural de 900 segundos.

El verificador usó `belenios-tool 3.3.0 (3.3.0) [debug]` de la imagen H1 fijada. Las custodias y el auditor fueron procesos del mismo host; no hubo revisión por un tercero humano independiente. No se ensayaron coerción, dispositivo hostil, todas las combinaciones de trustees, representación familiar jurídica ni OIDC. Estos resultados no autorizan elección vinculante, despliegue ni integración productiva.
