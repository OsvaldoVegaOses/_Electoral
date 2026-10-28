import hmac
import hashlib
import bcrypt
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User, AuditLog

logger = logging.getLogger("theogen.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# --- P13: Rate Limiter Persistente (Redis) ---
# Las funciones check_rate_limit, record_failed_attempt y clear_failed_attempts
# son provistas por el módulo rate_limiter, que usa Redis como backend compartido
# entre múltiples workers/instancias y tiene fallback automático a memoria.
from app.rate_limiter import check_rate_limit, record_failed_attempt, clear_failed_attempts, _mem_attempts  # noqa: F401
_failed_attempts = _mem_attempts


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


# --- P8: Hashing Criptográfico de Credenciales de Sufragio ---

def hash_voting_token(token: str) -> str:
    """
    P8: Derivación criptográfica HMAC-SHA256 para tokens de votación.
    Permite almacenar únicamente el hash en la base de datos (evitando que
    un volcado de la tabla voters exponga credenciales de sufragio válidas).
    """
    if not token or not token.strip():
        return ""
    key = settings.VOTE_HMAC_KEY.encode() if settings.VOTE_HMAC_KEY else b"theogen-voting-token-pepper"
    return hmac.new(key, token.strip().encode("utf-8"), hashlib.sha256).hexdigest()


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
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # P2: Extraer credencial desde cookie HttpOnly 'access_token' o cabecera 'Authorization: Bearer'
    effective_token = request.cookies.get(settings.AUTH_COOKIE_NAME) or token
    if not effective_token:
        raise credentials_exception
    try:
        payload = jwt.decode(
            effective_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
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
    IDOR-01 / RBAC / S2-A: Control de acceso a nivel de colegio/institución.
    - Superadmin: acceso global irrestricto.
    - Responsable Institucional: lectura y modificación exclusivamente de su institución asignada.
    - Comisión Electoral: solo lectura de su institución asignada (con election_id válido); no puede modificar la entidad colegio.
    """
    if is_superadmin(user):
        return
    if user.rol == ROLE_RESPONSABLE:
        if user.school_id is None or user.school_id != school_id:
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
        if user.school_id is None or user.school_id != school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: no tiene permisos para acceder a esta institución."
            )
        if user.election_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: comisión no asignada a esta elección."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado: permisos insuficientes para la institución."
    )


def _check_election_scope(user: User, election, write: bool = False):
    """
    IDOR-02 / RBAC / S2-A: Control de acceso a nivel de proceso electoral.
    - Superadmin: acceso total a todas las elecciones.
    - Responsable Institucional: acceso a todas las elecciones de su colegio (requiere school_id válido).
    - Comisión Electoral: acceso únicamente a su elección asignada (requiere obligatoriamente school_id
      y election_id coincidentes; si election_id es None o no coincide, denegar por defecto con 403).
    """
    if is_superadmin(user):
        return
    if user.rol == ROLE_RESPONSABLE:
        if user.school_id is None or user.school_id != election.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: la elección pertenece a otra institución o responsable sin institución asignada."
            )
        return
    if user.rol == ROLE_COMISION:
        if user.school_id is None or user.school_id != election.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: la elección pertenece a otra institución o comisión sin institución asignada."
            )
        if user.election_id is None or user.election_id != election.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: comisión no asignada a esta elección."
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acceso denegado: permisos insuficientes para la elección."
    )


def check_election_access(user: User, election, write: bool = False, allow_belenios: bool = False):
    _check_election_scope(user, election, write=write)
    if write:
        from sqlalchemy.orm import object_session
        from app.belenios.client import legacy_guard
        from app.models import Election
        session = object_session(election)
        if session is not None:
            session.query(Election).filter_by(id=election.id).populate_existing().with_for_update().one()
            if not allow_belenios:
                legacy_guard(session, election.id)


def validate_user_scope_assignment(
    rol: str,
    school_id: Optional[int],
    election_id: Optional[int],
    db: Optional[Session] = None
) -> None:
    """
    S2-A: Valida que las asignaciones school_id y election_id sean coherentes con el rol.
    - Superadmin / Administrador General: school_id=None, election_id=None.
    - Responsable Institucional: school_id obligatorio, election_id=None.
    - Comisión Electoral: school_id obligatorio, election_id obligatorio, y si db está presente,
      election.school_id == school_id.
    """
    if rol in (ROLE_SUPERADMIN, ROLE_LEGACY_ADMIN):
        if school_id is not None or election_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Administrador General no debe tener school_id ni election_id asignados."
            )
    elif rol == ROLE_RESPONSABLE:
        if school_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Responsable Institucional requiere un school_id válido."
            )
        if election_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Responsable Institucional no debe tener election_id asignado."
            )
    elif rol == ROLE_COMISION:
        if school_id is None or election_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Comisión Electoral requiere obligatoriamente school_id y election_id asignados."
            )
        if db is not None:
            from app.models import Election
            elec = db.query(Election).filter(Election.id == election_id).first()
            if not elec:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"La elección ID {election_id} no existe."
                )
            if elec.school_id != school_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Inconsistencia de ámbito: la elección no pertenece a la institución del usuario."
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Rol '{rol}' no reconocido."
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


# --- PII Minimization y Sanitización de Inyección de Fórmulas ---

def mask_email(email: Optional[str]) -> str:
    """
    Enmascara correos para registros de auditoría y protección de PII.
    Ejemplo: 'director@colegioa.cl' -> 'd***r@colegioa.cl'
             'ab@colegiob.cl'       -> 'a***@colegiob.cl'
    """
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = f"{local[0]}***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def sanitize_formula_injection(value: Optional[str]) -> Optional[str]:
    """
    Desactiva vectores de inyección de fórmulas CSV/Excel (CSV Formula Injection / DDE).
    Si el valor comienza con '=', '+', '-', '@', '\t' o '\r' (directamente o tras espacios iniciales),
    antepone un apóstrofe "'".
    """
    if not value or not isinstance(value, str):
        return value
    first_char = value[0] if len(value) > 0 else ""
    first_non_space = value.lstrip(" ")[0] if len(value.lstrip(" ")) > 0 else ""
    if first_char in ('=', '+', '-', '@', '\t', '\r') or first_non_space in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{value}"
    return value


# --- Auditoría Atómica y Trazabilidad Multi-Tenant (P15: Bitácora Append-Only Criptográfica) ---

GENESIS_HASH = "0" * 64


def format_audit_datetime(dt: datetime) -> str:
    """Formatea fecha a representación canónica UTC: YYYY-MM-DDTHH:MM:SS.ffffffZ"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_audit_hash(
    prev_hash: str,
    fecha: datetime,
    usuario: Optional[str],
    accion: str,
    detalle: Optional[str],
    school_id: Optional[int] = None
) -> str:
    """
    P15: Calcula el hash criptográfico SHA-256 canónico de un registro de auditoría.
    Formato canónico: {prev_hash}|{fecha_canonica}|{usuario}|{accion}|{detalle}|{school_id}
    """
    dt_str = format_audit_datetime(fecha)
    u = usuario or ""
    d = detalle or ""
    s = str(school_id) if school_id is not None else ""
    canonical = f"{prev_hash}|{dt_str}|{u}|{accion}|{d}|{s}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_audit_log_chain(db: Session, school_id: Optional[int] = None) -> dict:
    """
    P15: Verifica la integridad de la cadena criptográfica de la bitácora.
    Retorna un reporte detallando si la cadena está íntegra o el punto exacto de alteración.
    """
    query = db.query(AuditLog).order_by(AuditLog.id.asc())
    if school_id is not None:
        query = query.filter(AuditLog.school_id == school_id)
    logs = query.all()

    now_iso = datetime.now(timezone.utc).isoformat()

    if not logs:
        return {
            "integro": True,
            "total_revisados": 0,
            "primer_hash": None,
            "ultimo_hash": None,
            "fallo_en_id": None,
            "razon": None,
            "fecha_verificacion": now_iso,
        }

    expected_prev = GENESIS_HASH
    first_hash = logs[0].record_hash

    for i, log in enumerate(logs):
        # 1. Verificar prev_hash en eslabones intermedios
        if i > 0 and log.prev_hash != expected_prev:
            return {
                "integro": False,
                "total_revisados": i,
                "primer_hash": first_hash,
                "ultimo_hash": logs[i - 1].record_hash,
                "fallo_en_id": log.id,
                "razon": (
                    f"Eslabón roto en registro ID {log.id}: prev_hash '{log.prev_hash}' "
                    f"no coincide con hash anterior '{expected_prev}' "
                    f"(posible eliminación o inserción no autorizada)."
                ),
                "fecha_verificacion": now_iso,
            }

        # 2. Recomputar y verificar hash propio
        if log.record_hash:
            calculated = compute_audit_hash(
                log.prev_hash or GENESIS_HASH,
                log.fecha,
                log.usuario,
                log.accion,
                log.detalle,
                log.school_id
            )
            if log.record_hash != calculated:
                return {
                    "integro": False,
                    "total_revisados": i,
                    "primer_hash": first_hash,
                    "ultimo_hash": logs[i - 1].record_hash if i > 0 else None,
                    "fallo_en_id": log.id,
                    "razon": (
                        f"Contenido alterado en registro ID {log.id}: record_hash almacenado "
                        f"no coincide con el digest recomputado de los datos (posible manipulación de datos)."
                    ),
                    "fecha_verificacion": now_iso,
                }
            expected_prev = log.record_hash
        else:
            expected_prev = log.prev_hash or GENESIS_HASH

    return {
        "integro": True,
        "total_revisados": len(logs),
        "primer_hash": first_hash,
        "ultimo_hash": logs[-1].record_hash,
        "fallo_en_id": None,
        "razon": None,
        "fecha_verificacion": now_iso,
    }


def log_audit(
    db: Session,
    accion: str,
    detalle: Optional[str] = None,
    usuario: str = "Sistema",
    school_id: Optional[int] = None,
    commit: bool = True
) -> Optional[AuditLog]:
    """
    P15: Registra una acción en la bitácora append-only con encadenamiento criptográfico
    y trazabilidad multi-tenant.
    
    - Si commit=True (comportamiento por defecto): realiza db.commit() de inmediato.
    - Si commit=False: añade la entidad AuditLog a la sesión actual (db.add + db.flush) sin invocar
      commit() ni rollback(), permitiendo que la mutación de negocio y el registro de
      auditoría se confirmen o reviertan de forma estrictamente atómica dentro de la
      misma transacción.
    """
    try:
        # Obtener el último hash registrado en la cadena de auditoría
        last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
        prev_hash = last_log.record_hash if (last_log and last_log.record_hash) else GENESIS_HASH

        now = datetime.now(timezone.utc)
        record_hash = compute_audit_hash(prev_hash, now, usuario, accion, detalle, school_id)

        log = AuditLog(
            fecha=now,
            usuario=usuario,
            accion=accion,
            detalle=detalle,
            school_id=school_id,
            prev_hash=prev_hash,
            record_hash=record_hash,
        )
        db.add(log)
        db.flush()
        if commit:
            db.commit()
        return log
    except Exception as e:
        logger.error("Error al registrar auditoría: %s", e)
        if commit:
            db.rollback()
        else:
            raise


