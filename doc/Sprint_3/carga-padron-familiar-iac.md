# Carga del padrón familiar CPA IAC

El titular informó el 4 de noviembre de 2026 que la institución está construyendo el padrón. No se ha recibido ni cargado aquí el archivo real. La plataforma admite su incorporación desde la elección en borrador: **Padrón → Subir Padrón Excel / CSV**.

## Archivo y validaciones

Se admiten Excel `.xlsx` y CSV UTF-8, con o sin BOM, separado por coma, punto y coma o tabulación. El máximo es 10 MB por archivo. El formato `.xls` debe convertirse a `.xlsx` o CSV.

| Columna | Uso |
|---|---|
| RUT | Obligatorio; identificador del apoderado, con dígito verificador válido. No repetir el mismo RUT dentro de una elección. |
| Nombre | Obligatorio; nombre del apoderado. |
| Familia ID | Obligatorio en la regla «Un voto por familia»; identificador estable, sin utilizar datos de niños. |
| Correo | Dirección del apoderado; cuando se incluye se valida su formato. La entrega y el representante definitivo requieren su verificación propia. |
| Curso | Opcional; no determina la unidad familiar. |

Los integrantes de una misma familia deben compartir exactamente el mismo Familia ID. Familias distintas deben tener identificadores distintos. Dos apoderados de una familia son dos personas del padrón y una unidad electoral; esa repetición del identificador familiar es correcta. Los ceros iniciales de un identificador textual se conservan. La plataforma no deduce que dos personas son familia a partir del correo, apellido o curso.

Si falta la columna familiar, se rechaza el archivo antes de insertar. Si una fila no tiene Familia ID, se informa su número y motivo; las otras filas válidas se incorporan. Corregir y volver a cargar las filas pendientes: los RUT ya incorporados se rechazan como duplicados y no sobrescriben datos existentes. El resumen presenta personas leídas, incorporadas y rechazadas.

Después, revisar las familias y seleccionar exactamente un representante por unidad antes de vincular Belenios. La carga de padrón Belenios no emite tokens MVP ni envía credenciales o correos. La emisión de credenciales y su custodia conservan su proceso separado.

La carga respeta el ámbito institucional y se bloquea cuando el padrón queda congelado o la elección ya está vinculada a Belenios. Completar y cotejar el archivo antes de preparar esa vinculación. La carga de archivo no aumenta el límite actual de preparación del piloto Belenios: **100 unidades**, cuya ampliación y prueba de capacidad siguen pendientes para una elección mayor.

## Actualización de las decisiones de cierre

- Mayoría simple: mayor número de votos válidos; sin exigir más del 50 % ni participación mínima para contabilizar. El quórum de constitución de la asamblea se evalúa separadamente.
- En caso de empate, la presidencia se elige entre los directivos ya electos, según la indicación del titular. La plataforma no debe proclamar automáticamente a una persona por orden de lista, nombre o identificador. La resolución y la presidencia acordada deben registrarse en el acta correspondiente; no se inventa aquí quién realiza esa elección ni su mecanismo.
- Umbral de descifrado acordado: 3 de 5; modalidad acordada: presencial con los cinco y mínimo tres aportes individuales. La **ceremonia real sigue pendiente**, sin fecha ni ejecución confirmadas.
- Correo: el titular lo reporta operativo. La comprobación local del 4 de noviembre confirmó cuenta TRICEL, remitente activo y dominio autenticado. El readback Azure confirmó envío habilitado con `theogen@nubeweb.cl`; la nueva cuenta TRICEL permanece preparada para el cambio. Las consultas de cuenta desde la VM responden 200, y las de remitentes/dominio reciben 403/1010. Ese rechazo de consultas no prueba fallo de entrega. No se enviaron mensajes por esta revisión.

Las pruebas de carga usan personas y familias ficticias. Los archivos reales, identificadores personales y correspondencias de participantes permanecen fuera de Git.
