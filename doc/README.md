# Documentación de Infraestructura y Despliegue para Producción
### TheoGen Electoral — Participación transparente y verificable

Bienvenido a la documentación técnica de infraestructura para la puesta en producción de **TheoGen Electoral**. Este repositorio contiene las directrices, arquitecturas recomendadas, procedimientos operativos, políticas de seguridad y plantillas de configuración necesarias para operar la plataforma con alta disponibilidad, confidencialidad e integridad del proceso eleccionario.

---

## 📑 Estructura de la Documentación

| Documento | Descripción |
|---|---|
| [**01. Arquitectura de Infraestructura**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/01-arquitectura-infraestructura.md) | Topologías recomendadas (VPS, PaaS, Cloud), dimensionamiento de hardware (vCPU, RAM, SSD), diagrama de red y flujo de tráfico HTTPS seguro. |
| [**02. Guía de Despliegue Paso a Paso**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/02-guia-despliegue-produccion.md) | Manual de aprovisionamiento en servidor Linux (Ubuntu 22.04/24.04 LTS), Docker Engine, DNS, variables de entorno y puesta en marcha con Docker Compose. |
| [**03. Seguridad y Hardening**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/03-seguridad-y-hardening.md) | Configuración de cortafuegos (UFW), aislamiento de contenedores, certificados SSL/TLS con Let's Encrypt, Rate Limiting, cabeceras HTTP y custodia de claves criptográficas. |
| [**04. Respaldos y Recuperación ante Desastres**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/04-respaldos-y-recuperacion.md) | Políticas de respaldo (RTO / RPO), automatización con cron, almacenamiento externo cifrado, procedimientos de restauración y protocolo para el "Día de la Elección". |
| [**05. Monitoreo, Operaciones y Mantenimiento**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/05-monitoreo-y-mantenimiento.md) | Healthchecks (`/api/health`), rotación de logs (Docker logging driver), observabilidad de recursos, actualización continua y protocolo de emergencia. |

---

## 📦 Plantillas de Configuración Listas para Producción

En la carpeta [`doc/templates/`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/) se incluyen archivos listos para copiar y usar en el servidor productivo:

- [`docker-compose.prod.yml`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/docker-compose.prod.yml): Orquestación multi-contenedor para producción con redes internas aisladas, límites de recursos CPU/memoria y rotación de logs.
- [`nginx-ssl.conf`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/nginx-ssl.conf): Configuración para proxy reverso Nginx con terminación SSL/TLS 1.2/1.3, Rate Limiting para votaciones y cabeceras de seguridad estrictas.
- [`.env.production.example`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/.env.production.example): Plantilla de variables de entorno para producción con instrucciones de generación criptográfica.
- [`backup.sh`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/backup.sh): Script de respaldo automatizado de PostgreSQL con compresión y rotación de 30 días.
- [`restore.sh`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/restore.sh): Script de restauración controlada y validación de integridad de base de datos.

---

## 🚀 Resumen Rápido: Despliegue en 5 Pasos

```bash
# 1. Clonar el repositorio en el servidor de producción
git clone <URL_DEL_REPOSITORIO> /opt/theogen-electoral
cd /opt/theogen-electoral

# 2. Configurar el entorno de producción
cp doc/templates/.env.production.example .env
nano .env  # Asignar claves generadas con secrets de Python

# 3. Copiar la configuración de Docker Compose de producción
cp doc/templates/docker-compose.prod.yml docker-compose.prod.yml

# 4. Iniciar los servicios con Docker Compose
docker compose -f docker-compose.prod.yml up -d --build

# 5. Comprobar el estado y salud de la plataforma
curl -f http://localhost:8000/api/health
docker compose -f docker-compose.prod.yml ps
```

Para instrucciones detalladas paso a paso, consulte la [Guía de Despliegue Paso a Paso](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/02-guia-despliegue-produccion.md).

---

## 💻 Inicio Rápido en Servidor Local (Desarrollo)

Para iniciar el servidor en entorno local de desarrollo:

```powershell
cd "C:\Users\osval\OneDrive - ONG Tren Ciudadano\digital skills\theogen-electoral"
.\start.ps1
```