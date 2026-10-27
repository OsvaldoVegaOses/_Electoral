# 03. Seguridad y Hardening en Infraestructura
### TheoGen Electoral — Participación transparente y verificable

La seguridad en un sistema de votación electrónica no solo protege la infraestructura técnica, sino que resguarda la **legitimidad democrática y la fe pública** de los resultados. Este documento detalla las directrices de endurecimiento (*hardening*), políticas de red y protocolos criptográficos implementados en **TheoGen Electoral**.

---

## 🛡️ 1. Principios de Seguridad del Sistema

1. **Secreto del Voto:** La plataforma desacopla la identidad del elector de la papeleta de votación. El sistema verifica que el elector esté habilitado y pertenezca al padrón, marca su estado como "Ha votado", y registra el sufragio en la urna electrónica sin enlace directo reversible.
2. **Integridad Inmutable del Voto:** Cada voto emitido genera un comprobante con un **código hash HMAC-SHA256** generado con la clave privada del servidor (`VOTE_HMAC_KEY`). Cualquier modificación posterior en la base de datos invalida matemáticamente la comprobación.
3. **Mínimo Privilegio y Exposición Cero:** La base de datos PostgreSQL y la API interna no tienen exposición directa a Internet; únicamente el proxy reverso Nginx recibe conexiones públicas en los puertos 80 y 443.
4. **Trazabilidad Forense:** Toda acción administrativa (apertura, carga de padrón, emisión de voto, cierre, descarga de actas) queda registrada en la tabla inmutable `audit_logs` con marca de tiempo UTC y dirección IP.

---

## 🔒 2. Custodia y Gestión de Claves Criptográficas

El sistema depende críticamente de dos secretos criptográficos en el archivo `.env`:

| Variable | Tipo | Propósito | Criticidad |
|---|---|---|---|
| `SECRET_KEY` | Hexadecimal 64 bytes (256 bits) | Firma de tokens JWT para administradores y comisiones electorales. | **Máxima:** Si se compromete, un atacante podría forjar sesiones de administración. |
| `VOTE_HMAC_KEY` | Hexadecimal 32 bytes (128 bits) | Firma digital HMAC de los comprobantes de votación emitidos. | **Máxima:** Garantiza que los comprobantes provienen legítimamente del servidor. |
| `POSTGRES_PASSWORD` | Alfanumérico seguro (32+ caracteres) | Credencial de acceso a la base de datos PostgreSQL. | **Alta:** Protege el motor de base de datos interno. |

### Reglas de Custodia:
- **Generación en entorno seguro:** Genere siempre estas claves en el propio servidor de producción con `python3 -c "import secrets; print(secrets.token_hex(64))"`.
- **Nunca guardar en Git:** El archivo `.env` está expresamente excluido en el `.gitignore`.
- **Permisos de archivo restrictivos:**
  ```bash
  chmod 600 /opt/theogen-electoral/.env
  chown theogen:theogen /opt/theogen-electoral/.env
  ```
- **Inmutabilidad durante la elección:** **NUNCA** cambie `SECRET_KEY` ni `VOTE_HMAC_KEY` mientras una elección esté abierta. De lo contrario, se invalidarán las sesiones activas y la verificación de los hashes emitidos durante ese proceso.

---

## 🌐 3. Aislamiento de Red y Reglas de Cortafuegos

### 3.1. Configuración de UFW (Uncomplicated Firewall)
En el servidor host, solo deben estar abiertos los puertos indispensables:

```bash
# Estado de UFW recomendado
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Redirige a HTTPS)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

### 3.2. Aislamiento de Redes en Docker
El archivo `docker-compose.prod.yml` define dos redes virtuales aisladas:
1. `theogen_frontend_net`: Conecta el proxy reverso Nginx con el contenedor del frontend.
2. `theogen_backend_net`: Conecta Nginx con el backend FastAPI, y el backend con PostgreSQL.
- **Resultado:** El frontend nunca puede comunicarse directamente con la base de datos, y PostgreSQL no tiene pasarela hacia Internet.

---

## 🚦 4. Control de Tasa (Rate Limiting) y Mitigación de DoS

Para evitar ataques de saturación o intentos reiterados de votación fraudulenta, Nginx implementa zonas de limitación de tasa (*leaky bucket*):

```nginx
# Definición de zonas de memoria en nginx.conf
limit_req_zone $binary_remote_addr zone=vote_limit:10m rate=5r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# Aplicación en endpoint de votación
location /api/voting/vote {
    limit_req zone=vote_limit burst=10 nodelay;
    proxy_pass http://backend:8000/api/voting/vote;
}

# Aplicación en endpoint de login administrativo
location /api/auth/token {
    limit_req zone=login_limit burst=3 nodelay;
    proxy_pass http://backend:8000/api/auth/token;
}
```

---

## 🔐 5. Cabeceras HTTP de Seguridad (Security Headers)

Tanto Nginx como el middleware del backend (`SecurityHeadersMiddleware`) inyectan las cabeceras recomendadas por OWASP:

| Cabecera | Valor | Protección |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Fuerza a los navegadores a conectarse únicamente vía HTTPS. |
| `X-Content-Type-Options` | `nosniff` | Impide que el navegador interprete archivos MIME incorrectamente. |
| `X-Frame-Options` | `DENY` | Evita ataques de *Clickjacking* (prohíbe incrustar la app en `<iframe>`). |
| `X-XSS-Protection` | `1; mode=block` | Activa el filtro anti-XSS de navegadores heredados. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | No filtra URLs ni tokens en peticiones externas. |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Bloquea acceso a hardware del dispositivo del usuario. |
| `Content-Security-Policy` | Restricción de fuentes autorizadas (self, Google Fonts). | Previene ejecución de scripts no autorizados (XSS). |

---

## 💻 6. Endurecimiento del Servidor Linux (Host Hardening)

### 6.1. Configuración de SSH Seguro (`/etc/ssh/sshd_config`)
```ini
# Deshabilitar acceso directo de root
PermitRootLogin no

# Deshabilitar autenticación por contraseña (solo llaves SSH)
PasswordAuthentication no

# Limitar intentos de autenticación
MaxAuthTries 3

# Desconectar sesiones inactivas
ClientAliveInterval 300
ClientAliveCountMax 2
```
Reinicie el servicio tras aplicar los cambios:
```bash
sudo systemctl restart ssh
```

### 6.2. Protección con Fail2ban
Configure Fail2ban para bloquear automáticamente IPs con intentos sospechosos:

```ini
# /etc/fail2ban/jail.local
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = 22
```
```bash
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

---

## 🐳 7. Endurecimiento de Contenedores Docker

En el archivo de producción `docker-compose.prod.yml`:
- **Límites de Recursos:** Asignar `mem_limit` y `cpus` para evitar que un contenedor monopolice los recursos del servidor físico.
- **Prevención de Elevación de Privilegios:** Uso de `security_opt: [ "no-new-privileges:true" ]`.
- **Rotación de Logs:** Configurar el controlador `json-file` con `max-size: "10m"` y `max-file: "3"` para evitar que los archivos de registro colapsen el almacenamiento en disco.
- **Sin puertos de depuración:** En producción, la variable `ENVIRONMENT=production` deshabilita automáticamente la documentación interactiva Swagger (`/docs`) y ReDoc (`/redoc`).
