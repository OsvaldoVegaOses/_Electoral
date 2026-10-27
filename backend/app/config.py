import os
import secrets
import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger("theogen.config")


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

    # CORS — CRIT-03: Sin wildcard "*"
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

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

