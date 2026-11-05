# Accesos provisorios del ensayo

El acceso `/acceso/` obliga a reemplazar la contraseña provisoria antes de mostrar el enlace de la función. Las contraseñas de acceso se conservan únicamente como PBKDF2-SHA256, con 600 000 iteraciones, sal aleatoria y vencimiento inicial de 24 horas. Las sesiones limitadas duran 15 minutos; el cambio invalida todas las sesiones anteriores de ese usuario. Los formularios aplican origen, CSRF, cookies Secure/HttpOnly/SameSite y limitación de intentos.

Solo la cuenta administradora puede obtener la sesión nativa mediante `/api-token`. Se usa una identidad nativa dedicada, autorizada únicamente como propietaria del borrador de ensayo. La contraseña provisoria del portal no es válida en el login nativo; su secreto de servicio permanece en la configuración privada del servidor. La integración de sesión evita depender de la caché de contraseñas nativa, que conserva registros durante una hora. Los custodios y la autoridad de credenciales no reciben acceso administrativo.

Las contraseñas, correos personales, sesiones y enlaces de capacidad se provisionan fuera de Git. Las claves privadas de custodia y credenciales privadas de votación se generan bajo control de sus titulares, nunca por este servicio. Los correos iniciales identifican el acceso como contraseña de la plataforma y no como credencial de sufragio.

## Padrón CSV y demostración

La administración nativa admite cargar el archivo en la pestaña Votantes. El formato de ensayo es CSV UTF-8 **sin encabezado**, una línea por persona: `correo,identificador`, por ejemplo `persona@example.invalid,DEMO-01`. Se usa peso uno. Antes de la apertura se revisan las opciones, el padrón y el número de unidades.

El portal de la autoridad externa mantiene oculto su enlace hasta que el administrador confirme el padrón definitivo. La confirmación coteja el borrador nativo, exige entre 2 y 100 unidades de peso uno y destinatarios únicos, habilita únicamente esos correos en el puente y conserva la huella de la lista. Si cambia después, el enlace deja de habilitarse y se requiere conciliación. Una copia del CSV y sus datos identificatorios queda solo en el expediente privado del operador.

El padrón debe revisarse antes de generar credenciales. El cambio obligatorio de contraseña y la recepción del correo no prueban por sí solos elegibilidad electoral, custodia independiente ni verificación por tercero. El ensayo conserva su alcance no vinculante y la decisión del revisor queda pendiente conforme a la instrucción del titular.

## Despliegue acotado

El proceso escucha únicamente en loopback y se publica mediante el proxy HTTPS existente. Solo se añaden rutas de acceso, sesión nativa y salida; no se modifica la cabina, la criptografía, los votos, el verificador ni las partes de los custodios. El proceso no recibe claves Brevo, socket Docker ni privadas electorales. La configuración privada de la identidad nativa permite renovar su sesión y debe protegerse como secreto de servicio.

Variables: `ACCESS_STATE_DIR`, `ACCESS_PUBLIC_BASE`, `ACCESS_NATIVE_BRIDGE` y `ACCESS_MAIL_CONFIG`. El aprovisionamiento no forma parte del arranque público: no existe endpoint de alta libre. Las pruebas utilizan identidades y secretos sintéticos.

## Formulario de navegador e identidad IAC

La política `Referrer-Policy: no-referrer` provocaba `Origin: null` en el POST real del formulario, aunque una prueba HTTP con la cabecera Origin fijada manualmente pasara. El portal y su proxy usan ahora `same-origin`, con una sola cabecera efectiva en HTTPS. Se conserva el rechazo de orígenes ausentes, nulos o ajenos y los controles CSRF. Una regresión Chromium recorre la entrada, el cambio inicial y la revocación de la contraseña provisoria con una cuenta ficticia.

La presentación visible usa “Votación Centro de Padres IAC”, Instituto Abdón Cifuentes y el indicador de demostración no vinculante. El portal incluye esa identidad; las páginas nativas reciben únicamente una hoja de estilo y un script de presentación servido por el mismo origen. No se reescriben JavaScript criptográfico, JSON, enlaces, entradas de formulario ni archivos públicos de elección. La marca técnica y las fuentes originales permanecen en la página de información técnica y licencias. No se presenta el monograma tipográfico como un logotipo oficial del instituto.

El proxy requiere el módulo HTTP sub para añadir los recursos solamente a HTML. Los fragmentos `nginx-identity-locations.conf` y `nginx-identity-proxy.conf` se insertan respectivamente en el servidor HTTPS y en la ubicación de la interfaz nativa; probar siempre `nginx -t` antes de recargar. El directorio de código necesita permiso de recorrido por el usuario del servicio; el directorio de estado permanece privado.
