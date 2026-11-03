# Alcance y aceptación del piloto no vinculante

Corte: 2026-11-02. Este documento precisa los objetivos solicitados por el titular; no declara que estén implementados ni acepta el piloto. El ensayo MVP del 3 de noviembre y el piloto con secreto criptográfico tienen criterios distintos. No hay una fecha comprometida para cerrar todos los frentes siguientes.

## Capacidades y pruebas exigidas

| Frente | Estado en este corte | Entrega y criterio de aceptación |
|---|---|---|
| Piloto no vinculante | Ensayo individual MVP cerrado: una unidad ficticia, un voto y resultado consistente. No es una prueba de secreto | Nueva elección sintética Belenios, alcance informado, responsables y versión/entorno identificados; aceptación G3/M2 antes de incorporar participantes |
| Voto secreto y custodios | Integración experimental; worker nativo validado sobre tres archivos públicos anteriores y tres copias alteradas. Belenios no está habilitado en Azure | Cabina nativa que cifre antes de enviar, privadas de credenciales fuera de TheoGen, custodios en dominios administrativos independientes, umbral aprobado y ceremonia completa. Comprobar que el operador no pueda descifrar por sí solo y que sin umbral no haya escrutinio. Conservar límites y modelo de confianza |
| Verificación independiente | Servicio de verificación candidato, todavía no desplegado; pruebas de protocolo y aislamiento | Revisor ajeno a la operación obtiene por su cuenta el archivo y anclajes, verifica pruebas y conteos con versión fijada, firma/conserva su informe y recibo. Rechazar archivo alterado, antiguo o de otra elección. Un proceso separado bajo la misma administración no acredita independencia |
| Autenticación por estamento | Roles y entrega MVP existentes; el ensayo no prueba perfiles distintos | Matriz estamento → padrón habilitado → método de identidad → derecho de voto. Probar cada perfil admitido, recuperación, persona no habilitada, cambio de representante, cruce de institución/estamento y revocación antes de apertura. No habilitar un estamento que no haya completado su recorrido |
| Quórum y reglas | Configuración institucional pendiente; participación técnica no equivale a quórum | Política versionada y aprobada con denominador, instante de congelación, umbral, redondeo, blancos/nulos y empates. Separar quórum de Asamblea, participación electoral y mayorías de adjudicación. Casos por debajo, iguales y por encima del umbral; sin regla aprobada, resultado de quórum indeterminado |
| Repetición de elecciones | No queda resuelta mediante el bloqueo de una credencial usada ni mediante R1/R2 | Motivos y autoridad de repetición aprobados; cerrar/suspender según reglas, preservar expediente y crear nueva elección enlazada a la anterior, con nuevo identificador y credenciales propias. Probar no-quórum, empate/incidencia y límite de convocatorias aplicable. No resetear votos ni reutilizar credenciales de la elección anterior |
| Carga | El flujo de un elector y las pruebas CI no acreditan carga de destino | Base del ensayo: 40 unidades, hasta 50 sesiones y al menos 10 intentos inválidos/repetidos. Cero doble voto o pérdida de votos reconocidos; totales exactos; medir errores y p95. Objetivos propuestos: API p95 <3 s y confirmación <10 s; registrar cifrado por dispositivo. Ejecutar en entorno aislado equivalente, sin cargar la urna activa |
| Recuperación | Hay pruebas técnicas; falta recuperación electoral completa del destino | Ensayar caída de API/proveedor/BD, respuesta perdida, credencial perdida y fallo de custodio. Restaurar BD, estado Belenios y dependencias coordinadas en entorno aislado. Medir RPO/RTO contra objetivos previamente aceptados; conservar todos los votos reconocidos o detener el ejercicio y reportar la pérdida. La incertidumbre exige conciliación, no reintento ciego |
| Accesibilidad | Sin evidencia suficiente de aceptación del recorrido completo | Objetivo WCAG 2.2 AA para gestión, acceso, cabina nativa y resultados. Pruebas automáticas y manuales de teclado, foco, lector de pantalla, errores, zoom/reflujo, contraste, móviles y tiempos/códigos. Participantes de prueba con necesidades de accesibilidad validan tareas completas; fallos de la cabina externa también bloquean la aceptación de ese flujo |

## Identidad y unidad de voto

La matriz por estamento debe definirse con la institución: por ejemplo, representante de familia, estudiante o personal solo si forman parte de sus bases. No se presupone que todos voten en la misma urna ni con el mismo peso. SSO institucional, autenticación por correo/código u otro mecanismo son opciones a evaluar según identidad disponible, riesgo y recuperación; recibir un correo no demuestra por sí solo pertenencia al estamento.

La integración actual Belenios admite una credencial por unidad y peso uno, con selección única y sin blanco/nulo. Ponderaciones, papeletas múltiples y modalidades diferentes requieren diseño y pruebas adicionales en backend, cabina, cómputo, verificador e informes antes de activarse. No se atribuye soporte a toda opción que exista en el producto Belenios general.

El proceso debe separar: acreditación de identidad, habilitación del derecho, autenticación, emisión privada de credencial y cifrado del voto. El backend TheoGen no recibe preferencias ni privadas de Belenios. Los logs, correo y soporte se revisan para evitar reconstruir esa correspondencia. La administración, la autoridad de credenciales, los custodios y el revisor no se asignan automáticamente a los contactos aportados.

R1/R2 describe si se admite revotar dentro de una misma elección. Repetir una elección implica otra convocatoria y otra urna; ambas decisiones necesitan reglas propias. Las cifras estatutarias, periodos, mayorías y consecuencias no se inventan en el software.

## Secuencia de desarrollo y decisión

1. Terminar el candidato de verificador/runtime y los registros técnicos del MVP; validar CI en su SHA exacto. Esto no actualiza automáticamente Azure.
2. Desplegar el proveedor Belenios y el verificador en un entorno de piloto, con DNS/TLS, persistencia, secretos y manifiesto comprobados. Acordar responsables y política antes de crear una nueva elección sintética.
3. Probar el recorrido cifrado con autoridad externa de credenciales, custodios separados y verificación por un tercero. Usar un grupo de prueba suficiente: una elección de una persona revela su opción por el propio total y no demuestra privacidad útil.
4. Implementar y verificar los perfiles de identidad y reglas institucionales elegidos, incluyendo no-quórum y repetición. Mantener fuera de alcance las variantes aún no desarrolladas.
5. Ejecutar carga, recuperación y accesibilidad sobre la versión y topología candidatas; corregir fallos y repetir las comprobaciones afectadas.
6. Congelar SHA/digests/configuración, revisar evidencia técnica M1 y aceptación institucional G2, y decidir G3/M2 para el piloto no vinculante. G4 para uso vinculante conserva su evaluación propia.

Cada frente se cierra con informe que identifique SHA, imágenes, configuración sin secretos, fecha, datos sintéticos, procedimiento, resultado observado, fallos y responsable de revisión. La asistencia a una demostración no sustituye su aceptación. La independencia requiere evidencia de personas, acceso y custodia efectiva; ningún cambio de texto o test local la crea.

El 3 de noviembre solo puede presentarse como funcional el alcance realmente probado en el destino. Si el recorrido Belenios con custodios no está validado, el ensayo MVP conserva su advertencia de ausencia de secreto criptográfico y auditoría independiente. No se promete cerrar todos los requisitos por la llegada de una fecha.

## Fuentes técnicas

- [Belenios: cifrado en la cabina, credenciales y escrutinio](https://www.belenios.org/howitworks.html).
- [Belenios: límites y comportamiento operativo](https://www.belenios.org/faq.html). La integración TheoGen puede soportar un subconjunto.
- [W3C: WCAG 2.2](https://www.w3.org/TR/WCAG22/). Objetivo de aceptación; no certificación actual.
