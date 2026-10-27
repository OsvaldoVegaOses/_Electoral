from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
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
def login(login_data: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Inicia sesión con credenciales de Administrador o Comisión Electoral"""
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
    
    access_token = create_access_token(data={"sub": user.email, "rol": user.rol})
    log_audit(db, accion="Inicio de sesión", detalle=f"Usuario {user.email} ({user.rol}) inició sesión", usuario=user.email)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "nombre": user.nombre,
            "email": user.email,
            "rol": user.rol
        }
    }

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Retorna información del usuario actualmente autenticado"""
    return current_user
