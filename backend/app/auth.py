import bcrypt
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from collections import defaultdict
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, AuditLog

logger = logging.getLogger("theogen.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# --- CRIT-04: Rate Limiter en Memoria ---
_failed_attempts: dict[str, list[datetime]] = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutos
RATE_LIMIT_MAX_ATTEMPTS = 10


def check_rate_limit(
    client_ip: str,
    window: int = RATE_LIMIT_WINDOW_SECONDS,
    max_attempts: int = RATE_LIMIT_MAX_ATTEMPTS,
):
    """Verifica que la IP no haya excedido el límite de intentos"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=window)
    # Limpiar intentos expirados
    _failed_attempts[client_ip] = [
        t for t in _failed_attempts[client_ip] if t > cutoff
    ]
    if len(_failed_attempts[client_ip]) >= max_attempts:
        raise HTTPException(
            status_code=429,
            detail=f"Demasiados intentos. Intente nuevamente en {window // 60} minutos.",
        )


def record_failed_attempt(client_ip: str):
    """Registra un intento fallido para rate limiting"""
    _failed_attempts[client_ip].append(datetime.now(timezone.utc))


def clear_failed_attempts(client_ip: str):
    """Limpia los intentos fallidos al iniciar sesión exitosamente"""
    if client_ip in _failed_attempts:
        del _failed_attempts[client_ip]


# --- Hashing de contraseñas ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


# --- JWT Tokens ---

def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4()),  # LOW-01: JWT ID para futura revocación
    })
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def get_client_ip(request: Request) -> str:
    """Extrae la IP del cliente considerando cabeceras de proxy inverso (X-Forwarded-For)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# --- Dependencias de autenticación ---

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user


# --- HIGH-04: RBAC con require_role ---

def require_role(*allowed_roles):
    """
    Dependencia FastAPI que verifica que el usuario autenticado
    tenga uno de los roles permitidos.

    Uso:
        @router.post("/admin-only")
        def admin_endpoint(user: User = Depends(require_role("Administrador"))):
    """
    def _dependency(current_user: User = Depends(get_current_user)):
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere rol: {', '.join(allowed_roles)}",
            )
        return current_user
    return _dependency


# --- Auditoría ---

def log_audit(
    db: Session, accion: str, detalle: str = None, usuario: str = "Sistema"
):
    """Registra una acción en la bitácora de auditoría"""
    try:
        log = AuditLog(
            fecha=datetime.now(timezone.utc),
            usuario=usuario,
            accion=accion,
            detalle=detalle,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error("Error al registrar auditoría: %s", e)
        db.rollback()

