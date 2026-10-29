import os
import secrets
import logging
from pydantic_settings import BaseSettings
from pydantic import SecretStr

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
    # ADR-001: explicit laboratory mode; no production activation through this switch.
    BELENIOS_MODE: str = "off"
    BELENIOS_R1_URL: str = "http://127.0.0.1:18001"
    BELENIOS_R2_URL: str = "http://127.0.0.1:18002"
    BELENIOS_R1_ADMIN_TOKEN: SecretStr = SecretStr("")
    BELENIOS_R2_ADMIN_TOKEN: SecretStr = SecretStr("")
    BELENIOS_VERIFIER_IMAGE: str = ""
    BELENIOS_ALLOWED_HOSTS: str = ""
    BELENIOS_R1_PUBLIC_URL: str = ""
    BELENIOS_R2_PUBLIC_URL: str = ""
    BELENIOS_PILOT_APPROVAL: str = ""
    BELENIOS_APPROVED_SCHOOLS: str = ""
    BELENIOS_ALIAS_DOMAIN: str = ""
    BELENIOS_CA_FILE: str = ""
    BELENIOS_RUNTIME_MANIFEST: str = ""
    BELENIOS_RUNTIME_MANIFEST_SHA256: str = ""
    BELENIOS_VERIFIER_URL: str = ""
    BELENIOS_VERIFIER_TOKEN: SecretStr = SecretStr("")

    # Base de datos: Usa PostgreSQL si está configurado en env, o SQLite por defecto para desarrollo local
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./theogen_electoral.db")

    # JWT Autenticación — CRIT-01: Sin default predecible
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # MED-01: Reducido de 24h a 30 min

    # HMAC key para hashes de integridad de votos — MED-02
    VOTE_HMAC_KEY: str = os.getenv("VOTE_HMAC_KEY", "")
    # Clave independiente para seudonimizar unidades de sufragio.
    ENTITLEMENT_HMAC_KEY: str = os.getenv("ENTITLEMENT_HMAC_KEY", "")
    BREVO_API_KEY: SecretStr = SecretStr("")
    BREVO_SENDER_EMAIL: str = ""
    BREVO_SENDER_NAME: str = "TheoGen Electoral"
    BREVO_DELIVERY_ENABLED: bool = False
    PUBLIC_VOTING_URL: str = ""

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

if not settings.ENTITLEMENT_HMAC_KEY:
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "ENTITLEMENT_HMAC_KEY no configurada. Configure un secreto persistente "
            "independiente de SECRET_KEY y VOTE_HMAC_KEY."
        )
    logger.warning(
        "ENTITLEMENT_HMAC_KEY no configurada. Apertura y voto bloqueados hasta "
        "configurar la clave persistente independiente; no se genera una clave temporal."
    )
elif len(settings.ENTITLEMENT_HMAC_KEY.encode("utf-8")) < 32:
    raise RuntimeError("ENTITLEMENT_HMAC_KEY debe contener al menos 32 bytes.")
elif (settings.ENTITLEMENT_HMAC_KEY in (settings.SECRET_KEY, settings.VOTE_HMAC_KEY)
      or settings.ENTITLEMENT_HMAC_KEY.startswith(("CHANGE_ME", "CAMBIAR"))):
    raise RuntimeError("ENTITLEMENT_HMAC_KEY debe ser independiente y no un valor de ejemplo.")

if settings.ENVIRONMENT == "production":
    if any("localhost" in o or "127.0.0.1" in o for o in settings.BACKEND_CORS_ORIGINS):
        logger.warning(
            "⚠️ Producción configurada con orígenes CORS locales (localhost). "
            "Configure la variable BACKEND_CORS_ORIGINS con los dominios oficiales de producción."
        )

