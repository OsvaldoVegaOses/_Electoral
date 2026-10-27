import os
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.seed_data import seed_initial_data

# Importar Routers
from app.routers.auth import router as auth_router
from app.routers.schools import router as schools_router
from app.routers.elections import router as elections_router
from app.routers.voters import router as voters_router
from app.routers.candidates import router as candidates_router
from app.routers.voting import router as voting_router
from app.routers.reports import router as reports_router
from app.routers.audit import router as audit_router

logger = logging.getLogger("theogen.main")


# --- MED-05: Security Headers Middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Agrega headers de seguridad HTTP a todas las respuestas"""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Crear tablas en base de datos solo en desarrollo/test; en producción el esquema es gobernado por Alembic
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)
    else:
        logger.info("Entorno de producción: DDL automático deshabilitado; el esquema debe gestionarse exclusivamente mediante migraciones Alembic.")
    
    # 2. Cargar datos de demostración solo en desarrollo/test con opt-in explícito (B2: jamás en producción)
    seed_opt_in = os.getenv("SEED_DEMO_DATA", "false").lower() in ("true", "1", "yes")
    if settings.ENVIRONMENT in ["development", "test"] and seed_opt_in:
        db = SessionLocal()
        try:
            seed_initial_data(db)
        finally:
            db.close()
    elif settings.ENVIRONMENT == "production":
        logger.info("Entorno de producción: carga de datos demo omitida.")
        
    yield

# MED-01: Deshabilitar Swagger/ReDoc en producción
_docs_url = "/docs" if settings.ENVIRONMENT != "production" else None
_redoc_url = "/redoc" if settings.ENVIRONMENT != "production" else None

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API REST de TheoGen Electoral - Plataforma de Gestión de Procesos Electorales para Colegios, Centros de Padres y Organizaciones.",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# MED-05: Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# HIGH-07: Configuración de CORS — restringir métodos y headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Registro de Rutas API V1
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(schools_router, prefix=settings.API_V1_STR)
app.include_router(elections_router, prefix=settings.API_V1_STR)
app.include_router(voters_router, prefix=settings.API_V1_STR)
app.include_router(candidates_router, prefix=settings.API_V1_STR)
app.include_router(voting_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["General"])
def root():
    return {
        "sistema": settings.PROJECT_NAME,
        "subtitulo": settings.PROJECT_SUBTITLE,
        "version": settings.VERSION,
        "docs": _docs_url,
        "estado": "Operacional"
    }

# MED-04: Health check con timestamp dinámico
@app.get("/api/health", tags=["General"])
def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
