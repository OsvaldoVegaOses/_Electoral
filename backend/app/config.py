import os
import secrets
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger("theogen.config")


def _parse_cors_origins(raw_origins: str | None) -> list[str]:
    """
    Parsea los orígenes permitidos para CORS (P6).
    Acepta cadena separada por comas (ej. 'https://votacion.cl,https://admin.cl')
    o un arreglo JSON (ej. '["https://votacion.cl"]'). Fallback a puertos localhost de desarrollo.
    """
    default_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]
    if not raw_origins or not raw_origins.strip():
        return default_origins
    import json
    stripped = raw_origins.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(o).strip() for o in parsed if str(o).strip()]
        except Exception:
            pass
    return [o.strip() for o in stripped.split(",") if o.strip()]


class Settings(BaseSettings):
    PROJECT_NAME: str = "TheoGen Electoral"
    PROJECT_SUBTITLE: str = "Participación transparente y verificable"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Base de datos: Usa PostgreSQL si está configurado en env, o SQLite por defecto para desarrollo local
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./theogen_electoral.db")

    # JWT Autenticación — CRIT-01: Sin default predecible
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # MED-01: Reducido de 24h a 30 min

    # HMAC key para hashes de integridad de votos — MED-02
    VOTE_HMAC_KEY: str = os.getenv("VOTE_HMAC_KEY", "")

    # CORS — CRIT-03 & P6: Configurable desde variable de entorno BACKEND_CORS_ORIGINS
    BACKEND_CORS_ORIGINS: list[str] = _parse_cors_origins(os.getenv("BACKEND_CORS_ORIGINS"))

    # P13: Redis para rate limiting persistente multi-instancia.
    # Sin esta variable, el sistema usa fallback en memoria (no apto para prod multi-worker).
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # P14: Política de retención de PII
    # Días tras Finalización de elección antes de anonimizar padrón y comisiones electorales.
    PII_VOTER_RETENTION_DAYS: int = int(os.getenv("PII_VOTER_RETENTION_DAYS", "90"))
    # Días de retención de registros de auditoría antes de eliminarlos físicamente.
    PII_AUDIT_RETENTION_DAYS: int = int(os.getenv("PII_AUDIT_RETENTION_DAYS", "365"))

    # P2: Configuración de Cookies de Sesión y Protección CSRF
    AUTH_COOKIE_NAME: str = "access_token"
    CSRF_COOKIE_NAME: str = "csrf_token"
    COOKIE_SAMESITE: str = "lax"

    # S2-A: Bloqueo seguro por defecto de mutaciones destructivas de PII en producción
    PII_OPERATIONS_MUTATIONS_ENABLED: bool = os.getenv("PII_OPERATIONS_MUTATIONS_ENABLED", "false").lower() in ("true", "1", "yes")

    class Config:
        case_sensitive = True


settings = Settings()

# --- Validación de claves criptográficas al arranque ---

if not settings.SECRET_KEY:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "❌ SECRET_KEY no configurada. Genere una con:\n"
            "   python -c \"import secrets; print(secrets.token_hex(64))\""
        )
    else:
        settings.SECRET_KEY = secrets.token_hex(64)
        logger.warning("SECRET_KEY no configurada. Usando clave aleatoria temporal (sesiones no persistirán entre reinicios).")

if not settings.VOTE_HMAC_KEY:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "❌ VOTE_HMAC_KEY no configurada. Genere una con:\n"
            "   python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        settings.VOTE_HMAC_KEY = secrets.token_hex(32)
        logger.warning("VOTE_HMAC_KEY no configurada. Usando clave aleatoria temporal.")

if settings.ENVIRONMENT == "production":
    if any("localhost" in o or "127.0.0.1" in o for o in settings.BACKEND_CORS_ORIGINS):
        logger.warning(
            "⚠️ Producción configurada con orígenes CORS locales (localhost). "
            "Configure la variable BACKEND_CORS_ORIGINS con los dominios oficiales de producción."
        )


