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


# --- Roles del Sistema (A3 - P0) ---
ROLE_SUPERADMIN = "Administrador General"
ROLE_RESPONSABLE = "Responsable Institucional"
ROLE_COMISION = "Comisión Electoral"
ROLE_LEGACY_ADMIN = "Administrador"


def is_superadmin(user: User) -> bool:
    """Verifica si el usuario posee atribuciones globales de Administrador General"""
    return (user.rol == ROLE_SUPERADMIN) or (user.rol == ROLE_LEGACY_ADMIN and user.school_id is None)


def check_school_access(user: User, school_id: int, write: bool = False):
    """
    IDOR-01 / RBAC: Control de acceso a nivel de colegio/institución.
    - Superadmin: acceso global irrestricto.
    - Responsable Institucional: lectura y modificación exclusivamente de su institución asignada.
    - Comisión Electoral: solo lectura de su institución; no puede modificar la entidad colegio.
    """
    if is_superadmin(user):
        return
    if user.rol == ROLE_RESPONSABLE:
        if user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: no tiene permisos para acceder a esta institución."
            )
        return
    if user.rol == ROLE_COMISION:
        if write:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: comisiones electorales no poseen permisos de modificación sobre colegios."
            )
        if user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: no tiene permisos para acceder a esta institución."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado: permisos insuficientes para la institución."
    )


def check_election_access(user: User, election, write: bool = False):
    """
    IDOR-02 / RBAC: Control de acceso a nivel de proceso electoral.
    - Superadmin: acceso total a todas las elecciones.
    - Responsable Institucional: acceso a todas las elecciones de su colegio.
    - Comisión Electoral: acceso únicamente a su elección asignada (mismo colegio y election_id).
    """
    if is_superadmin(user):
        return
    if user.rol == ROLE_RESPONSABLE:
        if user.school_id != election.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: la elección pertenece a otra institución."
            )
        return
    if user.rol == ROLE_COMISION:
        if user.school_id != election.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: la elección pertenece a otra institución."
            )
        if user.election_id is not None and user.election_id != election.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: comisión no asignada a esta elección."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado: permisos insuficientes para la elección."
    )


# --- HIGH-04: RBAC con require_role ---

def require_role(*allowed_roles):
    """
    Dependencia FastAPI que verifica que el usuario autenticado
    tenga uno de los roles permitidos.
    """
    def _dependency(current_user: User = Depends(get_current_user)):
        # Si es superadmin y "Administrador" o "Administrador General" está permitido
        if is_superadmin(current_user) and any(r in [ROLE_SUPERADMIN, ROLE_LEGACY_ADMIN] for r in allowed_roles):
            return current_user
        if current_user.rol not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permisos insuficientes. Se requiere rol: {', '.join(allowed_roles)}",
            )
        return current_user
    return _dependency


# --- Auditoría ---

def log_audit(
    db: Session, accion: str, detalle: str = None, usuario: str = "Sistema", school_id: Optional[int] = None
):
    """Registra una acción en la bitácora de auditoría con trazabilidad multi-tenant"""
    try:
        log = AuditLog(
            fecha=datetime.now(timezone.utc),
            usuario=usuario,
            accion=accion,
            detalle=detalle,
            school_id=school_id
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error("Error al registrar auditoría: %s", e)
        db.rollback()


