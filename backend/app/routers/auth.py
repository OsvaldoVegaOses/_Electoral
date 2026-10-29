import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserLogin, Token, UserResponse
from app.auth import (
    verify_password, create_access_token, get_current_user,
    log_audit, check_rate_limit, record_failed_attempt, clear_failed_attempts,
    get_client_ip
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Inicia sesión con credenciales de Administrador o Comisión Electoral (P2: Cookie HttpOnly + CSRF)"""
    # CRIT-02: Rate limiting por IP
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)

    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        # CRIT-02: Registrar intento fallido
        record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Limpiar intentos fallidos al tener éxito
    clear_failed_attempts(client_ip)
    
    access_token = create_access_token(data={
        "sub": user.email,
        "rol": user.rol,
        "school_id": user.school_id,
        "election_id": user.election_id
    })
    csrf_token = secrets.token_hex(32)

    # P2: Fijar cookie HttpOnly para el JWT y cookie estándar para el token CSRF
    is_secure = settings.ENVIRONMENT == "production"
    cookie_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite=settings.COOKIE_SAMESITE,
        max_age=cookie_max_age,
        path="/",
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # JavaScript debe poder leerlo para adjuntarlo en cabecera X-CSRF-Token
        secure=is_secure,
        samesite=settings.COOKIE_SAMESITE,
        max_age=cookie_max_age,
        path="/",
    )

    log_audit(
        db,
        accion="Inicio de sesión",
        detalle=f"Usuario {user.email} ({user.rol}) inició sesión",
        usuario=user.email,
        school_id=user.school_id
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "csrf_token": csrf_token,
        "user": {
            "id": user.id,
            "nombre": user.nombre,
            "email": user.email,
            "rol": user.rol,
            "school_id": user.school_id,
            "election_id": user.election_id
        }
    }


@router.post("/logout")
def logout(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """P2: Cierra la sesión invalidando las cookies HttpOnly y CSRF en el navegador"""
    response.delete_cookie(key=settings.AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/")

    log_audit(
        db,
        accion="Cierre de sesión",
        detalle=f"Usuario {current_user.email} ({current_user.rol}) cerró sesión",
        usuario=current_user.email,
        school_id=current_user.school_id
    )
    return {"message": "Sesión cerrada correctamente"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Retorna información del usuario actualmente autenticado"""
    return current_user
