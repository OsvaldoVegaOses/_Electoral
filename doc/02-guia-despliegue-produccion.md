# 02. Guía de Despliegue Paso a Paso en Servidor Linux
### TheoGen Electoral — Participación transparente y verificable

Esta guía detalla el procedimiento completo para aprovisionar y desplegar **TheoGen Electoral** en un servidor con **Ubuntu 22.04 LTS o 24.04 LTS** en producción, utilizando Docker Compose, Nginx y certificados SSL Let's Encrypt.

---

## 📋 Requisitos Previos

1. **Servidor Linux:** VPS o servidor dedicado (mínimo 2 vCPU, 4 GB RAM, 25 GB SSD).
2. **Dominio configurado:** Nombre de dominio o subdominio apuntando a la IP pública del servidor (ej. `votaciones.theogen.cl` con registro DNS de tipo `A`).
3. **Acceso SSH:** Acceso como usuario `root` o usuario con privilegios `sudo`.

---

## 🛠️ Paso 1: Aprovisionamiento y Actualización del Sistema Operativo

Conéctese al servidor por SSH y ejecute la actualización inicial de paquetes:

```bash
# Actualizar lista de paquetes y dependencias del sistema
sudo apt update && sudo apt upgrade -y

# Instalar utilitarios esenciales
sudo apt install -y curl wget git ufw fail2ban htop jq software-properties-common ca-certificates gnupg lsb-release
```

### Crear usuario de despliegue dedicado (Buena práctica)
Evite ejecutar la aplicación directamente como `root`:

```bash
# Crear usuario 'theogen'
sudo adduser --gecos "" theogen
sudo usermod -aG sudo theogen

# Copiar llaves SSH al nuevo usuario
sudo mkdir -p /home/theogen/.ssh
sudo cp /root/.ssh/authorized_keys /home/theogen/.ssh/
sudo chown -R theogen:theogen /home/theogen/.ssh
sudo chmod 700 /home/theogen/.ssh
sudo chmod 600 /home/theogen/.ssh/authorized_keys
```

---

## 🐳 Paso 2: Instalación de Docker Engine y Docker Compose

Instale la versión oficial más reciente de Docker desde los repositorios oficiales de Docker:

```bash
# 1. Agregar clave GPG oficial de Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 2. Configurar el repositorio apt de Docker
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Instalar Docker Engine, CLI y Compose Plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Habilitar servicio y agregar usuario al grupo docker
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker theogen

# 5. Validar instalación
docker --version
docker compose version
```

---

## 🔒 Paso 3: Configuración del Cortafuegos (UFW)

Proteja el servidor bloqueando todos los puertos innecesarios:

```bash
# Reglas por defecto: denegar entrante, permitir saliente
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Permitir SSH (puerto 22 o el puerto personalizado configurado)
sudo ufw allow 22/tcp

# Permitir tráfico web HTTP y HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Activar firewall
sudo ufw --force enable
sudo ufw status verbose
```

> [!NOTE]
> Observe que **no** abrimos los puertos `5432` (PostgreSQL) ni `8000` (FastAPI). Solo estarán accesibles internamente en la red de Docker.

---

## 📂 Paso 4: Clonar el Repositorio de la Plataforma

Cree la carpeta `/opt/theogen-electoral` y clone el proyecto:

```bash
sudo mkdir -p /opt/theogen-electoral
sudo chown -R theogen:theogen /opt/theogen-electoral

# Cambiar al usuario theogen y directorio de la aplicación
su - theogen
cd /opt/theogen-electoral

# Clonar el repositorio
git clone <URL_REPOSITORIO_GIT> .
```

---

## 🔑 Paso 5: Configurar Variables de Entorno Seguras

Genere contraseñas y claves criptográficas robustas utilizando el módulo `secrets` de Python:

```bash
# Generar claves criptográficas en terminal
echo "POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(64))')"
echo "VOTE_HMAC_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Copie la plantilla de producción y edite el archivo `.env`:

```bash
cp doc/templates/.env.production.example .env
chmod 600 .env  # Restringir permisos de lectura solo al usuario theogen
nano .env
```

Asegúrese de configurar los siguientes valores reales:
```ini
ENVIRONMENT=production

POSTGRES_DB=theogen_electoral
POSTGRES_USER=theogen
POSTGRES_PASSWORD=<PASSWORD_GENERADA_32_CHARS>

DATABASE_URL=postgresql://theogen:<PASSWORD_GENERADA_32_CHARS>@db:5432/theogen_electoral

SECRET_KEY=<SECRET_KEY_GENERADA_64_HEX>
VOTE_HMAC_KEY=<VOTE_HMAC_KEY_GENERADA_32_HEX>

# Dominio público real
DOMAIN=votaciones.theogen.cl
```

---

## 🌐 Paso 6: Configurar Dominio y Certificados SSL (Let's Encrypt)

### Opción A: Con Certbot en el Host (Recomendado y más simple)

```bash
# Instalar Certbot y plugin de Nginx
sudo apt install -y certbot python3-certbot-nginx nginx

# Detener temporalmente nginx local si está activo para emitir el certificado
sudo systemctl stop nginx

# Solicitar certificado SSL Let's Encrypt para su dominio
sudo certbot certonly --standalone -d votaciones.theogen.cl --email soporte@theogen.cl --agree-tos --no-eff-email

# Los certificados se guardarán en:
# /etc/letsencrypt/live/votaciones.theogen.cl/fullchain.pem
# /etc/letsencrypt/live/votaciones.theogen.cl/privkey.pem
```

Configure la renovación automática periódica en `cron`:
```bash
sudo systemctl enable certbot.timer
sudo certbot renew --dry-run
```

---

## 🚀 Paso 7: Despliegue de Contenedores con Docker Compose

Copie el archivo de Docker Compose optimizado para producción:

```bash
cp doc/templates/docker-compose.prod.yml docker-compose.prod.yml

# Construir imágenes e iniciar contenedores en segundo plano
docker compose -f docker-compose.prod.yml up -d --build
```

Compruebe que todos los contenedores inicien correctamente:

```bash
docker compose -f docker-compose.prod.yml ps
```

Deberá observar:
```
NAME                 STATUS                   PORTS
theogen_db           Up (healthy)             (puerto interno 5432)
theogen_backend      Up                       127.0.0.1:8000->8000/tcp
theogen_frontend     Up                       127.0.0.1:3000->80/tcp
theogen_nginx        Up                       0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

## ✅ Paso 8: Verificación y Pruebas Post-Despliegue

1. **Verificar Endpoint de Salud del Backend:**
   ```bash
   curl -f http://127.0.0.1:8000/api/health
   # Respuesta esperada: {"status":"ok","timestamp":"..."}
   ```

2. **Verificar Logs del Backend:**
   ```bash
   docker compose -f docker-compose.prod.yml logs backend --tail 50
   ```
   Asegúrese de ver:
   - `INFO: Database tables created/verified.`
   - `INFO: Seed data check completed.`
   - `Uvicorn running on http://0.0.0.0:8000`

3. **Verificar Acceso HTTPS Externo:**
   Abra en su navegador web `https://votaciones.theogen.cl`:
   - El candado SSL debe aparecer en verde/válido.
   - La pantalla de votación `/votar` debe cargar rápidamente.
   - El acceso al panel administrativo debe exigir las credenciales maestras.

---

## 🔄 Paso 9: Procedimiento de Actualización de Versiones (Deploy Continuo)

Cuando se publiquen cambios de código en Git, actualice el servidor sin perder datos:

```bash
cd /opt/theogen-electoral

# 1. Obtener la última versión estable
git pull origin main

# 2. Reconstruir los contenedores con mínimo downtime
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d --no-deps backend frontend

# 3. Limpiar imágenes antiguas no utilizadas
docker image prune -f

# 4. Confirmar salud operativa
docker compose -f docker-compose.prod.yml ps
```
