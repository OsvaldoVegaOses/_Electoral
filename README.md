# TheoGen Electoral
### *Participación transparente y verificable*

Plataforma DEMO / MVP de **Gestión Electoral Digital** orientada a colegios, centros de padres, centros de estudiantes, juntas de vecinos, organizaciones sociales y asociaciones comunitarias.

El objetivo de esta versión DEMO es validar integralmente la **experiencia del usuario y los flujos operacionales** con directores de establecimientos y dirigentes de centros de padres, permitiendo constatar valor comercial inmediato antes de incorporar criptografía de alta complejidad.

---

## 🏛️ Arquitectura del Sistema

```
   ┌──────────────────────────────────────────────┐
   │         Frontend Web (React + Vite)          │
   │           Material UI (MUI) Design           │
   │  Dashboard • Hub Elección • /votar Pública   │
   └──────────────────────┬───────────────────────┘
                          │ REST API / JWT
                          ▼
   ┌──────────────────────────────────────────────┐
   │           Backend (Python FastAPI)           │
   │        SQLAlchemy ORM • ReportLab PDF        │
   │       Validador RUT Módulo 11 • Hashes       │
   └──────────────────────┬───────────────────────┘
                          │
                          ▼
   ┌──────────────────────────────────────────────┐
   │       Base de Datos Relacional               │
   │    PostgreSQL (Docker) / SQLite (Local)      │
   └──────────────────────────────────────────────┘
```

---

## 🚀 Módulos Implementados

| Módulo | Funcionalidad | Descripción |
|---|---|---|
| **Módulo 1** | **Crear Elección** | Formulario para configurar Nombre, Descripción, Fechas, Institución y Tipo de Elección (*Centro de Padres, Centro de Alumnos, Consejo Escolar, Consulta Ciudadana, Directiva Organización*). |
| **Módulo 2** | **Carga de Padrón** | Subida masiva en Excel (.xlsx, .xls) o CSV con columnas `RUT`, `Nombre`, `Curso`, `Correo`, `Familia ID`. Validación matemática de RUT chileno (Módulo 11), detección de correos inválidos, control de duplicados y reporte visual de errores por fila. |
| **Módulo 3** | **Reglas Electorales** | Soporte para **"Un voto por persona"** o **"Un voto por familia"**. En votaciones familiares, cuando un apoderado sufraga, el sistema bloquea automáticamente a los demás miembros con el mismo `familia_id`. |
| **Módulo 4** | **Generación de Credenciales** | Emisión automática de tokens criptográficos UUID v4 únicos por elector. Simulador de despacho de correos electrónicos con plantilla HTML y enlaces de acceso directo `/votar?token=...`. |
| **Módulo 5** | **Pantalla de Votación Pública** | URL pública `/votar` accesible sin login. Validación en tiempo real del token, presentación de listas, opciones de **Voto en Blanco** y **Voto Nulo**, confirmación irreversible y emisión de comprobante con **Hash de Integridad (SHA-256)**. |
| **Módulo 6** | **Dashboard en Tiempo Real** | Panel de control con métricas clave: Total Padrón, Votos Emitidos, Participación %, Votos Pendientes y gráficos visuales de barras y distribución de sufragios. |
| **Módulo 7** | **Escrutinio Definitivo** | Cómputo oficial al cerrar la elección: recuento por lista, votos blancos, nulos, tasa de participación y proclamación destacada de la opción ganadora. |
| **Módulo 8** | **Actas Automáticas en PDF** | Generación y descarga directa con ReportLab: **Acta de Apertura** (constatación de urna en cero, miembros de comisión y firmas) y **Acta de Cierre** (escrutinio definitivo, participación, firmas y certificación). |
| **Módulo 9** | **Bitácora de Auditoría** | Registro inmutable (`AuditLog`) con fecha, usuario, acción (*Creó elección, Subió padrón, Abrió votación, Emitió voto, Cerró votación, Descargó acta*) y detalle de la operación. |
| **Módulo 10** | **Identidad de Marca TheoGen** | Paleta corporativa con Azul Marino (`#0d233a`), Azul Cívico (`#1e40af`), Blanco y Gris Claro, con imagotipo institucional y subtítulo oficial. |

---

## 📋 Credenciales y Datos Demo Precargados

Al iniciar por primera vez, el sistema ejecuta automáticamente un **Seed de Datos** que incluye:

### 1. Usuarios Administrativos
- **Administrador General:**
  - Correo: `admin@theogen.cl`
  - Contraseña: `admin123`
- **Comisión Electoral:**
  - Correo: `comision@theogen.cl`
  - Contraseña: `comision123`

### 2. Proceso Electoral de Demostración
- **Institución:** Colegio San Gabriel de Las Condes (RBD 10245-8)
- **Elección:** *Elección Centro General de Padres y Apoderados 2026-2027* (Estado: **Abierta**)
- **Regla:** Un voto por familia
- **Comisión Electoral:** 3 miembros acreditados (Presidenta, Secretario, Vocal)
- **Candidatos Registrados:**
  1. *Lista A: Innovación y Familia* (Carolina Valenzuela)
  2. *Lista B: Comunidad Unida* (Andrés Morales)
  3. *Lista C: Futuro Escolar* (Marcela Soto)
  4. *Voto en Blanco*
  5. *Voto Nulo*

### 3. Electores y Tokens de Votación para Pruebas Inmediatas
Ingrese a [http://localhost:5173/votar](http://localhost:5173/votar) y utilice cualquiera de los siguientes tokens de prueba:

| Elector | RUT | Grupo Familiar | Token UUID de Prueba | Comportamiento |
|---|---|---|---|---|
| **Francisca Silva Montes** | 16.234.567-2 | `FAM-101` | `3a8f803d-0ccb-48b7-89f7-d92aa4c729de` | Voto habilitado |
| **Rodrigo Silva Montes** | 15.890.123-K | `FAM-101` | `b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e` | Mismo grupo: si Francisca ya votó, el sistema bloqueará este token por regla familiar. |
| **Camila Vergara Pinto** | 17.123.456-7 | `FAM-102` | `c2d3e4f5-6a7b-8c9d-0e1f-2a3b4c5d6e7f` | Voto habilitado |
| **Felipe Errázuriz Lyon** | 18.345.678-4 | `FAM-103` | `d3e4f5a6-7b8c-9d0e-1f2a-3b4c5d6e7f8a` | Voto habilitado |

---

## ⚡ Instalación y Ejecución

### Opción 1: Despliegue con Docker Compose (Un solo comando)
Requiere tener Docker instalado:
```bash
docker compose up --build
```
Una vez iniciado:
- **Frontend Web:** [http://localhost:3000](http://localhost:3000) o [http://localhost](http://localhost)
- **Sala de Votación:** [http://localhost:3000/votar](http://localhost:3000/votar)
- **Documentación Swagger API:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Opción 2: Ejecución Local Rápida (Windows)
En caso de preferir ejecutarlo de inmediato sin contenedores:

#### Con Script Automático:
Haga doble clic en `start.bat` o ejecute en PowerShell:
```powershell
.\start.ps1
```

#### Manualmente en dos terminales:
**Terminal 1 (Backend FastAPI):**
```bash
cd backend
.\venv\Scripts\python.exe main.py
```
*API disponible en http://localhost:8000/docs con base de datos SQLite automática.*

**Terminal 2 (Frontend React):**
```bash
cd frontend
npm run dev
```
*Aplicación disponible en http://localhost:5173*

---

## 🎯 Flujo de Validación del MVP (Demo Walkthrough)

Para comprobar el cumplimiento de los requerimientos ante un cliente o directivo:

1. **Ingresar a la plataforma:** Vaya a `http://localhost:5173` y observe las métricas del Dashboard en tiempo real.
2. **Revisar la Elección:** En la sección Elecciones, ingrese a la *Elección Centro General de Padres y Apoderados*.
3. **Padrón Electoral:** Explore la pestaña "Padrón Electoral" donde constan los 20 electores con sus RUTs validados y grupos familiares. Descargue la plantilla Excel o pruebe la carga masiva.
4. **Despacho de Credenciales:** En la pestaña "Generador de Credenciales", haga clic en *"Simular Envío Masivo de Correos"* para visualizar los correos generados con tokens.
5. **Emitir Sufragio:**
   - Abra una ventana de incógnito o nueva pestaña en `http://localhost:5173/votar`.
   - Ingrese el token `3a8f803d-0ccb-48b7-89f7-d92aa4c729de`.
   - Seleccione una de las listas o candidatos y confirme su voto.
   - Observe la animación de celebración y el **Comprobante Digital con Hash de Integridad SHA-256**.
6. **Validar Regla Familiar:**
   - Intente votar inmediatamente con el token `b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e` (perteneciente a la misma familia `FAM-101`).
   - El sistema le informará con total claridad que la familia ya emitió su voto.
7. **Cerrar Elección y Generar Actas:**
   - Como Administrador o Comisión, cierre la votación.
   - Descargue el **Acta de Apertura (PDF)** y el **Acta de Cierre y Escrutinio (PDF)** generadas con ReportLab, listas para imprimir y firmar.
8. **Consultar Auditoría:**
   - Ingrese a la pestaña *Auditoría* y compruebe cómo cada acción (apertura, emisión de voto con hash, descargas) quedó registrada en la bitácora inmutable.

---

## 📚 Infraestructura y Despliegue en Producción

La carpeta [`doc/`](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/) contiene la documentación técnica completa para el despliegue en servidores productivos:

- [**01. Arquitectura de Infraestructura**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/01-arquitectura-infraestructura.md): Diagrama de red, dimensionamiento de servidores y aislamiento de contenedores.
- [**02. Guía de Despliegue Paso a Paso**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/02-guia-despliegue-produccion.md): Aprovisionamiento en Linux Ubuntu, Docker Compose y certificados SSL Let's Encrypt.
- [**03. Seguridad y Hardening**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/03-seguridad-y-hardening.md): Cortafuegos (UFW), Rate Limiting, cabeceras de seguridad y custodia de claves criptográficas.
- [**04. Respaldos y Recuperación ante Desastres**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/04-respaldos-y-recuperacion.md): Automatización con cron, RTO/RPO y protocolo para el "Día de la Elección".
- [**05. Monitoreo y Mantenimiento**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/05-monitoreo-y-mantenimiento.md): Healthchecks `/api/health`, rotación de logs, observabilidad y solución de incidencias.
- [**Plantillas de Producción**](file:///c:/Users/osval/OneDrive%20-%20ONG%20Tren%20Ciudadano/digital%20skills/theogen-electoral/doc/templates/): Archivos `docker-compose.prod.yml`, `nginx-ssl.conf`, scripts de backup y `.env.production.example`.

---

## 📄 Licencia y Derechos
Desarrollado para **TheoGen Electoral** © 2026. Todos los derechos reservados.
