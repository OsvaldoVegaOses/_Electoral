# Prueba en producción con 1.000 electores sintéticos

El titular autorizó probar los cambios en producción e informó aproximadamente 1.000 electores. El alcance técnico es una elección sintética separada: carga, lectura completa, controles de acceso y configuración de cinco custodios con umbral tres. No se cargan familias reales ni se emiten credenciales o mensajes. La ceremonia humana, sufragio y descifrado reales conservan su evaluación pendiente.

El candidato reúne los cambios de los PR 16, 17 y 18. El máximo de preparación se amplía de 100 a **1.000 unidades** en el backend y el portal nativo. La lectura del portal deja de truncar respuestas mayores de 64 KiB, conservando un máximo de 4 MiB. La interfaz obtiene el padrón en páginas de 500, rechaza páginas repetidas y evita usar una lectura incompleta. Las unidades con un solo integrante usan ese representante; las de varios integrantes requieren selección explícita y la confirmación general del operador.

Antes del despliegue: CI completa del commit, respaldo PostgreSQL e inventario de la versión, registros existentes y borrador nativo. El despliegue conserva el correo y las claves de los usuarios. La migración de custodia es aditiva y no asigna política retroactiva a vinculaciones previas.

## Comprobaciones previstas

- Cargar 1.000 personas ficticias con identificadores familiares y correos no entregables.
- Recuperar las 1.000 personas por API y navegador, sin quedarse en las primeras 100 o 500.
- Rechazar duplicados, acceso anónimo, ausencia de CSRF y preparación fuera de la capacidad.
- Comprobar 1.000 unidades en un borrador Belenios nuevo y cinco custodios ficticios con umbral tres, sin generar sus claves privadas ni abrirlo.
- Comparar las huellas de los datos anteriores y del borrador previo, sin alterar su configuración ni ceremonia.
- Registrar tiempos observados, versión, digests y resultados. Una prueba de carga del padrón no equivale a 1.000 votos concurrentes ni a escrutinio criptográfico completo.

Los resultados y cualquier incidencia deben registrarse después de ejecutar las comprobaciones, sin declarar éxito a partir de esta planificación. Los informes operativos y secretos permanecen en `.runtime`; únicamente evidencia sanitizada puede incorporarse al repositorio.
