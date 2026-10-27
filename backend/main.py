import os
import secrets
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.seed_data import seed_initial_data
import app.rate_limiter as rate_limiter

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


# --- P2: CSRF Protection Middleware (Double Submit Cookie) ---
class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    P2: Valida protección CSRF para mutaciones (POST, PUT, DELETE, PATCH)
    cuando la petición está autenticada mediante cookie HttpOnly.
    """
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXCLUDED_PREFIXES = (
        f"{settings.API_V1_STR}/auth/login",
        f"{settings.API_V1_STR}/voting/",
        f"{settings.API_V1_STR}/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    )

    async def dispatch(self, request: Request, call_next):
        if request.method not in self.SAFE_METHODS:
            has_auth_cookie = bool(request.cookies.get(settings.AUTH_COOKIE_NAME))
            has_auth_header = bool(request.headers.get("Authorization"))

            # Aplica solo si la sesión está basada en cookie y no tiene cabecera Authorization (modo browser)
            if has_auth_cookie and not has_auth_header:
                path = request.url.path
                if not any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
                    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
                    csrf_header = request.headers.get("X-CSRF-Token")

                    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
                        logger.warning(
                            f"Petición rechazada por CSRF inválido o ausente en {path}"
                        )
                        return JSONResponse(
                            status_code=status.HTTP_403_FORBIDDEN,
                            content={"detail": "Token CSRF inválido o ausente en cabecera X-CSRF-Token"}
                        )
        return await call_next(request)



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
        
    # P13: Inicializar cliente Redis para rate limiting persistente
    rate_limiter._init_redis(settings.REDIS_URL)

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

# P2: CSRF protection middleware
app.add_middleware(CSRFProtectionMiddleware)

# MED-05: Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# HIGH-07: Configuración de CORS — restringir métodos y headers (incluyendo X-CSRF-Token)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-CSRF-Token"],
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

# MED-04 & P7: Health check con verificación real de conectividad a Base de Datos
@app.get("/api/health", tags=["General"])
def health_check():
    db_status = "ok"
    http_code = status.HTTP_200_OK
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Healthcheck BD fallido: {exc}")
        db_status = "error"
        http_code = status.HTTP_503_SERVICE_UNAVAILABLE

    payload = {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }
    return JSONResponse(status_code=http_code, content=payload)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
