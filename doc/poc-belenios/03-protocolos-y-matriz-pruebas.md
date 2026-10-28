# H2 — Protocolo de prueba ejecutado

Fecha: 2026-10-28. [G1 aprobado](00a-autorizacion-g1.md). Las dos elecciones principales usan Belenios 3.3.0 fijado en H0/H1, diez unidades ficticias cada una, una pregunta homomórfica A/B de selección obligatoria y peso 1. No se modela blanco/nulo ni se atribuye validez jurídica.

## Secuencia reproducible

Desde `poc/belenios-3.3.0/`, con H1 comprobado:

```powershell
python tests/setup_h2.py
cd tests
npm ci --ignore-scripts
npx playwright install chromium
node vote_ui.mjs
cd ..
python tests/prepare_api_ballots.py
cd tests
node vote_api.mjs
cd ..
python tests/tally_h2.py
python tests/prepare_faults.py
cd tests
node faults.mjs
node capture_results.mjs
cd ..
python tests/publish_public.py
```

Se usaron Playwright 1.64.1 y Chromium instalado para pruebas, con contextos nuevos y bloqueo de solicitudes del navegador fuera de cada origen local. El conector de navegador interactivo no estaba disponible; estas pruebas ejecutaron la interfaz original mediante el runner de regresión, no una UI alternativa del adaptador. No se capturaron pantallas de credenciales/OTP. La instalación de Chromium no se repitió en este equipo porque ya estaba disponible.

Los scripts de preparación rechazan repetir creación cuando existe estado local. Los journals privados distinguen inicio, prevalidación y confirmación; un resultado incierto exige cotejar boleta/cabeza pública antes de continuar. **No ejecutar la secuencia otra vez sobre los mismos datos esperando una elección nueva**. Para un ensayo nuevo, archivar evidencia y preparar otro laboratorio controlado; no borrar datos ajenos ni hacer prune global.

## Autoridades y confianza

- Las credenciales de las elecciones principales se generaron con `belenios-tool setup generate-credentials` en contenedores sin red y directorios de autoridad separados de los volúmenes de urna. La distribución se simuló entregando a cada contexto de votante solo su credencial.
- Tres custodias de prueba completaron certificados y pasos Pedersen por CLI/API; las claves privadas nunca se subieron al API. Se usaron dos de tres, además del componente `server` documentado por upstream.
- Esto demuestra separación de procesos/activos de laboratorio, no operadores humanos independientes: todo se ejecutó bajo control del mismo host. No se ejercitó el protocolo nuevo de credential operator/server ni un servidor de credenciales de otro administrador.
- La verificación se ejecutó en otro contenedor sin red, filesystem de solo lectura y únicamente el directorio público montado. Es verificación separada del proceso de urna, no auditoría independiente por otra persona/máquina física.

## Matriz de evidencia

| Caso | Ejecución observada | Alcance |
|---|---|---|
| BEL-01 | H1: 29 comprobaciones, build y dos urnas aisladas | Debug de laboratorio; determinismo total de dependencias no demostrado |
| BEL-02 | Dos elecciones, 10 unidades cada una, padrón/configuración fijados antes de apertura | Solo identidades ficticias |
| BEL-03 | Autoridad manual por CLI, subida pública y sufragio con privadas fuera de urna | Protocolo operator/server y separación administrativa real pendientes |
| BEL-04 | Ceremonia 2/3, ausencia de trustee 3 en A y 2 en B; un aporte no permite publicar; dos sí | No se ensayó la ausencia del trustee 1 ni todas las combinaciones |
| BEL-05 | 20 votos iniciales por UI original; inclusión/trackers y resultado comprobados | Sin malware/coacción simulados |
| BEL-06 | Segundo voto por UI y luego por API aceptado en A; solo la última boleta de la credencial queda activa | Archivo conserva historia |
| BEL-07 | B rechaza segundo voto por UI y API con `RevoteNotAllowed`; cabeza/boletas no cambian | No es una garantía contra root/rollback malicioso |
| BEL-08 | Una identidad/credencial por unidad sintética; no hay dos credenciales para una familia | Representantes familiares, discrepancias y estatutos siguen en H4/G2 |
| BEL-09 | Ambos archivos finales verificados, exit 0 y resultado presente | Mismo host; entorno separado sin secretos |
| BEL-10 | Alteración del payload de resultado detectada, exit 124; prefijo válido sin resultado puede pasar | Requiere anclar cabeza final y exigir resultado |
| BEL-11 | Crear/editar borrador, padrón, credenciales públicas, trustees, fases, descarga, resultados; errores 400/401/403/404/409/412/500 | No se ejecutó cada endpoint de H0 ni todos los servicios de autenticación |
| BEL-12 | Reinicio conserva boletas/cabeza; invalida token; fixture adicional prueba credencial incorrecta, cierre de navegador, refresh, doble submit, sesión perdida y elección cerrada | Timeout natural de 900 s y entrega a votante sin correo no demostrados |
| BEL-13 | Solo datos ficticios, correo fuera del árbol web, urnas sin ruta externa; escaneo de archivos públicos contra secretos conocidos | Captura exhaustiva de egress y análisis de metadatos pendientes |
| BEL-14 | Conteos y participación exportables desde evidencia ya verificada en H3 | Plantilla jurídica, quórum y firmas no aprobados |
| BEL-15 | Factibilidad documental en H0 | OIDC no ejecutado, opcional posterior |

El fixture de fallos es otra elección sintética descartable con credenciales y clave de servidor. Esa configuración deliberadamente débil solo sirve para errores/interrupciones: no se confunde con las dos elecciones principales de autoridad manual y umbral.

**Cierre:** se verificó el recorrido funcional necesario para H3 experimental. No se declara GO de toda la PoC, cumplimiento jurídico, anonimato absoluto ni aprobación de G2/G3/G4. Los límites de la matriz permanecen visibles en el informe final.
