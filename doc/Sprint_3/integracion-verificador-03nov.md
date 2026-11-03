# Integración del candidato de verificador y runtime Belenios

Corte de preparación: 2026-11-03. El titular solicitó integrar el candidato y ejecutar la CI completa. La integración técnica se tramita mediante una rama y PR contra `main`; no activa Belenios en Electoral ni sustituye las aceptaciones del piloto.

## Cambios del candidato

- Verificador con colector autenticado y worker sin red, entrada limitada a archivos públicos, enlace entre UUID y Setup, comprobación nativa del resultado final y rechazo de contenido alterado. El backend exige commit, digest de herramienta, resultado verificado y SHA-256 coincidentes antes de aceptar el archivo.
- Empaquetado del tag anotado Belenios 3.3.0, receta release y guardas de configuración explícita. El Dockerfile del verificador comprueba acceso al ejecutable como UID 10001; corrige el permiso de travesía observado en la imagen base.
- Transporte nativo de autenticación por Brevo con destinatario autorizado y registro durable del intento. Una respuesta incierta requiere conciliación; no se reenvía automáticamente. No se emiten credenciales privadas de Belenios desde TheoGen.
- PDF de apertura y cierre del MVP como registros técnicos, sin proclamaciones, validez institucional ni firmas inferidas. Los datos se tratan como texto y no se incluyen identificadores ni contactos de revisores.
- Pruebas nuevas y documentación de [alcance del piloto](alcance-piloto-no-vinculante.md), [custodia](configuracion-avanzada-secreto.md) y [ejercicio criptográfico](ejercicio-belenios-03nov.md).

Se excluyen los cambios pendientes del directorio principal en scripts de preflight/smoke Brevo y sus pruebas, archivos de entorno, configuración privada, claves, contactos y registros operativos. No se cambian las migraciones, las guardas de activación ni los datos históricos de votos.

## Evidencia disponible antes de congelar el commit

Las 67 pruebas focalizadas locales pasaron. La construcción del verificador `ch1s` pasó con digest `sha256:a8a34da5893706e161db4cb3c6cffdba3009cf85e7e2c2232f68ee90acb99ce6`; no es una ejecución de CI completa del repositorio. El ejercicio de cinco votos sintéticos completó las tres parejas 2/3 y rechazó cero/un aporte externo, dos aportes sin componente servidor y una copia alterada del archivo. El [informe sanitizado](evidencias/ejercicio-belenios-03nov.json) conserva ese corte previo, con `candidate_committed=false` y `full_candidate_ci=false` como hechos históricos.

La CI completa debe identificar el SHA congelado y aprobar los diez controles de [CI Azure](ci-azure.md): PostgreSQL 16/Redis 7, backend y migraciones/concurrencia/restore sin omisiones, lint/build, E2E reales, UI Belenios con dobles, auditorías Python/npm, secretos de archivos e historial y Compose/Nginx. La evidencia retenida por digest y el estado del commit se enlazan desde el PR. Se verifica que `main` no haya avanzado antes de fusionar y se repite la CI sobre el SHA resultante de la integración.

## Límites que conserva la integración

La instancia Electoral conserva `BELENIOS_MODE=off`. Los servicios externos del ensayo no se actualizan por fusionar este candidato. El archivo criptográfico y sus partes se generaron bajo un único operador; el ensayo no acredita independencia de personas ni voto por cabina HTTPS. Las funciones propuestas, la autoridad externa de credenciales, el revisor y M1/M2/G2/G3/G4 mantienen sus criterios propios. La CI no contacta destinos productivos ni envía correos.
