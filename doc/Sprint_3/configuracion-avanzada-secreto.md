# Brechas para secreto con custodios independientes

Corte de revisión: 2026-11-02. El objetivo es un piloto no vinculante con cifrado y confianza distribuida. Este diagnóstico no habilita Belenios ni designa autoridades. El [plan de aceptación](alcance-piloto-no-vinculante.md) incluye los demás frentes del piloto.

## Avance del 3 de noviembre

El [ejercicio criptográfico actualizado](ejercicio-belenios-03nov.md) completó cinco votos sintéticos y verificó las tres parejas del umbral 2/3. Cero o un aporte externo, y dos aportes sin componente del servidor, fueron rechazados. El worker aceptó el archivo válido y rechazó su copia alterada. La imagen corregida del verificador se construyó en ACR `ch1s` y sustituyó los dos servicios; se corrigió el permiso de travesía que impedía ejecutar la herramienta con UID 10001. Las partes fueron simuladas bajo un operador; no hay custodia humana independiente acreditada. La [evidencia de este corte](evidencias/ejercicio-belenios-03nov.json) conserva la comprobación final. Los apartados siguientes describen el diagnóstico del 2 de noviembre y sus brechas; los puntos de construcción y combinaciones de parejas se actualizan por este avance.

## Qué existía y qué probaba al 2 de noviembre

- `backend/app/belenios/service.py::transition` ya exige `credentials_ready`, `trustees_ready`, tipo Threshold, tres custodios y umbral dos antes de validar la elección. Esa comprobación describe capacidades del proveedor; no comprueba independencia humana ni quién puede acceder a los equipos.
- El laboratorio H2 completó una ceremonia 2/3, sufragios cifrados y escrutinio, incluyendo rechazo de publicación con un solo aporte. Todo estuvo bajo un mismo host/operador. No se probaron todas las combinaciones de ausencia. Véanse [protocolo](../poc-belenios/03-protocolos-y-matriz-pruebas.md) y [resultado](../poc-belenios/04-resultados-verificacion.md).
- El candidato de desarrollo pasó 91 pruebas focalizadas de verificador, contrato, guard de release, PDF e integración. El worker nativo aceptó tres archivos públicos de laboratorio y rechazó sus tres copias alteradas. Son evidencias locales; no son CI completa del SHA final, despliegue ni auditoría externa.
- Se preparó el contexto público del tag anotado Belenios 3.3.0, commit `337887bd1862c7cd057080b530fd80941bfc3c69`, mediante `git archive`. La construcción local de la imagen de verificador agotó 240 s; la conciliación posterior no encontró la etiqueta candidata ni contenedores activos. No se repitió. La imagen release y el arranque Compose no están validados.
- El resultado del backend conserva `independent_custody_confirmed: false`. El motor MVP conserva correlación histórica entre elector y selección; las correcciones de texto/PDF no modifican esa propiedad.
- Una consulta de solo lectura a Azure confirmó la revisión `electoral-production-trial--s3-808eb03-mail` y `BELENIOS_MODE=off`. El candidato local no cambió ese destino.

## Brechas ordenadas y evidencia para cerrarlas

| Prioridad | Trabajo concreto | Responsable y salida verificable |
|---|---|---|
| 1. Modelo de confianza y responsables | Acordar el alcance frente al operador, autoridad de credenciales, custodios, proveedor y dispositivos; ratificar 2/3 para este piloto o diseñar y volver a probar otro umbral | Institución y responsables del piloto. Identificar administrador de urna, autoridad externa de credenciales, tres custodios y revisor independiente, con aceptación de funciones y conflictos. Los contactos aportados no son designaciones |
| 2. Runtime fuera del laboratorio | Construir imagen release fijada, revisar mantenimiento/avisos de la versión elegida y validar servidor, cabina y verificador. Preparar HTTPS, persistencia, backup, secretos mínimos y dominios administrativos separados | Ingeniería y operación. CI del SHA exacto, digests, configuración revisada, manifiesto de runtime vigente y pruebas de inicio/aislamiento. El backend no monta Docker ni obtiene claves de custodios |
| 3. Autoridad externa de credenciales | Elegir generación manual oficial o protocolo credential operator/server; operarla bajo control ajeno a la urna. Entregar privadas directamente a cada participante y publicar únicamente el material público requerido | Autoridad de credenciales. Prueba de emisión, entrega y recuperación de la misma credencial sin crear otro derecho, sin privadas en TheoGen, logs, backups generales o cuenta Brevo compartida con el operador. La modalidad operator/server sigue sin ensayo integral |
| 4. Identidad operativa | Resolver cómo el alias aleatorio de cada unidad autentica al representante correcto. La integración actual prepara `Configured,email`; el dominio/relay y su correspondencia real no quedan resueltos al configurar Brevo | Responsable de identidad y autoridad de credenciales. Probar OTP/entrega, persona incorrecta, representante alternativo y recuperación. OIDC u otro método necesita integración explícita y sus pruebas, no solo activar una variable |
| 5. Ceremonia con tres custodios | Cada custodio genera y conserva su parte privada en su equipo/control. Completar el protocolo nativo, cotejar públicas/huellas y mantener enlaces de capacidad protegidos | Custodios y operador de ceremonia. Acta técnica sin secretos, claves públicas cotejadas, controles de acceso y respaldo individual. El operador no debe poder leer dos partes ni sus copias de respaldo. Tres cuentas dentro de un host accesible por el mismo root no bastan |
| 6. Revisión y custodia externa | Desplegar el verificador y completar observación de continuidad, anclajes finales y recibos. El revisor obtiene archivo/referencias por su cuenta y ejecuta su comprobación en otro entorno bajo su control | Revisor/custodio externo. Informe con UUID, versión, imagen, archivo SHA-256, cabeza final, resultado y recibo autenticado. Las nuevas cabeceras del servicio no constituyen prueba de independencia; el prototipo anterior no cumple el nuevo contrato |
| 7. Ensayo integral y fallos | Crear nuevas elecciones sintéticas separadas del MVP y del laboratorio previo; votar desde cabina nativa, cerrar y escrutar con custodios reales | Ingeniería, participantes de prueba y custodios. Cada pareja 1+2, 1+3 y 2+3 debe permitir escrutinio con el componente servidor requerido; cero o un custodio no. Probar aporte incorrecto/repetido, pérdida de acceso, respuesta incierta, archivo antiguo/alterado y restauración coordinada |
| 8. Revisión para activar piloto | Congelar versión/configuración y revisar evidencias, riesgos, pendientes e información a participantes | Revisión técnica M1 y aceptación institucional G2/G3/M2. Mantener Belenios apagado hasta satisfacer los gates aplicables. La elección vinculante conserva G4 propio |

## Precisiones de seguridad

La configuración 3.3.0 examinada incluye un componente de descifrado del servidor además del umbral externo. No se afirma que la urna carezca de todo material privado: debe demostrarse que ese componente no permite escrutar sin los aportes externos requeridos y que puede recuperarse de forma controlada.

No hace falta que cada custodio opere un servidor permanente; sí necesita control efectivo de su dispositivo, claves, enlaces privados y respaldo. Concentrar las partes suficientes o sus backups en un Key Vault/host accesible por el mismo operador destruye la separación que se pretende acreditar.

El cifrado se realiza en la cabina del participante. Se debe revisar qué código sirve la cabina y qué información sale del navegador: no enviar selección en claro a TheoGen ni permitir que logs o soporte reconstruyan la preferencia. Un grupo de una persona revela su opción por el total; el ensayo de privacidad exige varios participantes y también examinar riesgos de grupos pequeños/unanimidad.

El umbral distribuye confianza; no elimina la colusión de quienes reúnen suficientes partes. Tampoco resuelve por sí solo dispositivo infectado, cabina alterada o coacción. Esos límites deben permanecer en el modelo de amenazas y la información del piloto.

## Próximo trabajo que puede avanzar sin designaciones

Cerrar construcción/arranque del candidato con contexto público y pruebas de aislamiento; documentar la topología y accesos; preparar el guion y los formatos públicos de ceremonia/recibos; implementar pruebas faltantes de combinaciones y recuperación sobre elecciones nuevas. Ninguna de esas tareas necesita recibir las claves privadas de futuros custodios.

Las entradas humanas que condicionan la activación son: responsables que aceptan sus funciones, ratificación del umbral/política, destino bajo control separado, método de identidad y disponibilidad para la ceremonia. Deben resolverse antes del ensayo real, sin convertir esas decisiones en valores inventados del código.

## Valor de activación y configuración pendiente

El código actual reconoce `off`, `laboratory` y `pilot` en sus guardas. `BELENIOS_MODE=on` no habilita la integración. `laboratory` solo funciona con entorno development; en Azure el modo aplicable sería `pilot`, conservando `ENVIRONMENT=production`.

Para el perfil elegido, por ejemplo R2, deben provisionarse y verificarse:

- `BELENIOS_PILOT_APPROVAL`: referencia real de aceptación del piloto, y `BELENIOS_APPROVED_SCHOOLS`: instituciones concretas autorizadas. Escribir una referencia en una variable no constituye su aprobación.
- `BELENIOS_R2_URL` y `BELENIOS_R2_PUBLIC_URL`: servidor y cabina HTTPS operativos; `BELENIOS_ALLOWED_HOSTS`: destinos permitidos; `BELENIOS_R2_ADMIN_TOKEN`: secreto administrativo con acceso mínimo. R1 solo se configura si su política forma parte del alcance.
- `BELENIOS_RUNTIME_MANIFEST` y `BELENIOS_RUNTIME_MANIFEST_SHA256`: archivo montado, observado por el operador, con commit/digest/política/URL y referencia coincidentes. La vigencia aceptada es como máximo 24 horas; no usar un manifiesto de ejemplo como evidencia.
- `BELENIOS_ALIAS_DOMAIN`: dominio operativo con autenticación/entrega probadas para los alias de las unidades.
- `BELENIOS_VERIFIER_URL`, `BELENIOS_VERIFIER_TOKEN` y `BELENIOS_VERIFIER_IMAGE`: servicio HTTPS funcionando y digest inmutable compatible. `BELENIOS_CA_FILE` solo si la CA configurada lo requiere.

La función `enabled()` comprueba modo, entorno, referencia y ámbito institucional. Las operaciones posteriores comprueban destinos, token, versión/API y manifiesto; validar la elección exige además credenciales públicas y ceremonia 2/3 listas. Que `enabled()` devuelva verdadero no demuestra que todos esos pasos funcionen ni que exista custodia independiente.

El cambio de modo no convierte la elección MVP cerrada en una urna Belenios ni asigna custodios. El siguiente hito técnico es un proveedor release y verificador desplegados y validados; después, una elección nueva con autoridad externa y ceremonia real.

Fuentes primarias: [Belenios: funcionamiento](https://www.belenios.org/howitworks.html), [configuración y autoridades](https://www.belenios.org/setup.html), [umbral y límites](https://www.belenios.org/faq.html). El comportamiento concreto de 3.3.0 se contrasta con el commit fijado y las pruebas del repositorio; la documentación general no sustituye esa validación.
