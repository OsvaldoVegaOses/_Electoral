from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
import re

# --- USUARIOS Y AUTENTICACIÓN ---
class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)

class UserCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    rol: Optional[str] = None
    school_id: Optional[int] = None
    election_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """HIGH-04: Validación mínima de complejidad de contraseña"""
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("La contraseña debe contener al menos una letra")
        if not re.search(r"[0-9]", v):
            raise ValueError("La contraseña debe contener al menos un número")
        return v

    @model_validator(mode="after")
    def validate_scope_consistency(self) -> "UserCreate":
        """S2-A: Valida consistencia obligatoria entre rol y asignación de colegio/elección"""
        if self.rol is None:
            if self.school_id is None and self.election_id is None:
                self.rol = "Administrador General"
            elif self.school_id is not None and self.election_id is None:
                self.rol = "Responsable Institucional"
            elif self.school_id is not None and self.election_id is not None:
                self.rol = "Comisión Electoral"
            else:
                raise ValueError("Asignación inválida: election_id requiere un school_id")

        rol = self.rol
        if rol in ("Administrador General", "Administrador"):
            if self.school_id is not None or self.election_id is not None:
                raise ValueError("Administrador General no debe tener school_id ni election_id asignados")
        elif rol == "Responsable Institucional":
            if self.school_id is None:
                raise ValueError("Responsable Institucional requiere un school_id válido")
            if self.election_id is not None:
                raise ValueError("Responsable Institucional no debe tener election_id asignado")
        elif rol == "Comisión Electoral":
            if self.school_id is None:
                raise ValueError("Comisión Electoral requiere un school_id asignado")
            if self.election_id is None:
                raise ValueError("Comisión Electoral requiere un election_id asignado")
        else:
            raise ValueError(f"Rol desconocido: {rol}")
        return self

class Token(BaseModel):
    access_token: str
    token_type: str
    csrf_token: Optional[str] = None
    user: dict

class UserResponse(BaseModel):
    id: int
    nombre: str
    email: EmailStr
    rol: str
    school_id: Optional[int] = None
    election_id: Optional[int] = None

    class Config:
        from_attributes = True

# --- COLEGIO / ORGANIZACIÓN ---
class SchoolBase(BaseModel):
    nombre: str
    rbd: Optional[str] = None
    comuna: Optional[str] = None
    correo_contacto: Optional[str] = None
    telefono: Optional[str] = None
    logo: Optional[str] = None

class SchoolCreate(SchoolBase):
    pass

class SchoolUpdate(BaseModel):
    nombre: Optional[str] = None
    rbd: Optional[str] = None
    comuna: Optional[str] = None
    correo_contacto: Optional[str] = None
    telefono: Optional[str] = None
    logo: Optional[str] = None


class SchoolResponse(SchoolBase):
    id: int
    fecha_creacion: datetime

    class Config:
        from_attributes = True

# --- COMISIÓN ELECTORAL ---
class ElectoralCommitteeBase(BaseModel):
    nombre: str
    rut: str
    correo: Optional[str] = None
    cargo: str  # Presidente, Secretario, Vocal

class ElectoralCommitteeCreate(ElectoralCommitteeBase):
    pass

class ElectoralCommitteeResponse(ElectoralCommitteeBase):
    id: int
    election_id: int

    class Config:
        from_attributes = True

# --- CANDIDATO ---
class CandidateBase(BaseModel):
    nombre: str
    cargo: Optional[str] = None
    descripcion: Optional[str] = None
    foto: Optional[str] = None
    orden: Optional[int] = 0
    es_blanco: Optional[bool] = False
    es_nulo: Optional[bool] = False

class CandidateCreate(CandidateBase):
    pass

class CandidateResponse(CandidateBase):
    id: int
    election_id: int
    votos_count: Optional[int] = 0

    class Config:
        from_attributes = True

# --- ELECTOR / PADRÓN ---
class VoterBase(BaseModel):
    rut: str
    nombre: str
    curso: Optional[str] = None
    correo: Optional[str] = None
    familia_id: Optional[str] = None

class VoterCreate(VoterBase):
    pass

class VoterResponse(VoterBase):
    id: int
    estado: str
    fecha_voto: Optional[datetime] = None
    election_id: int

    class Config:
        from_attributes = True

class VoterBulkUploadResult(BaseModel):
    total_leidos: int
    total_validos: int
    total_errores: int
    errores: List[dict]
    insertados: int

# --- ELECCIÓN ---
class ElectionBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    school_id: int
    tipo_votacion: str = "Centro de Padres"
    regla_votacion: str = "Un voto por persona"

class ElectionCreate(ElectionBase):
    committee: Optional[List[ElectoralCommitteeCreate]] = []

class ElectionUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fecha_inicio: Optional[datetime] = None
    fecha_fin: Optional[datetime] = None
    estado: Optional[str] = None
    tipo_votacion: Optional[str] = None
    regla_votacion: Optional[str] = None

class ElectionResponse(ElectionBase):
    id: int
    estado: str
    config_hash: Optional[str] = None
    fecha_cierre_efectiva: Optional[datetime] = None
    total_padron_congelado: Optional[int] = None
    total_habilitados_congelado: Optional[int] = None
    config_snapshot: Optional[str] = None
    fecha_creacion: datetime
    school: Optional[SchoolResponse] = None

    class Config:
        from_attributes = True

class ElectionDetailResponse(ElectionResponse):
    committee_members: List[ElectoralCommitteeResponse] = []
    candidates: List[CandidateResponse] = []
    total_voters: int = 0
    voted_count: int = 0

# --- VOTACIÓN PÚBLICA ---
class TokenValidateRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=256)

class TokenValidateResponse(BaseModel):
    valido: bool
    mensaje: str
    elector_nombre: Optional[str] = None
    eleccion_nombre: Optional[str] = None
    eleccion_tipo: Optional[str] = None
    regla_votacion: Optional[str] = None
    colegio_nombre: Optional[str] = None
    candidatos: List[CandidateResponse] = []

class VoteSubmitRequest(BaseModel):
    token: str
    candidate_id: int

class VoteReceiptResponse(BaseModel):
    success: bool
    mensaje: str
    hash_integridad: str
    fecha_voto: datetime
    eleccion_nombre: str
    colegio_nombre: str

# --- RESULTADOS Y ESCRUTINIO ---
class CandidateResult(BaseModel):
    candidate_id: int
    nombre: str
    cargo: Optional[str] = None
    descripcion: Optional[str] = None
    votos: int
    porcentaje: float
    es_blanco: bool = False
    es_nulo: bool = False

class ScrutinyResponse(BaseModel):
    election_id: int
    election_nombre: str
    estado: str
    total_padron: int
    total_votos: int
    participacion_porcentaje: float
    votos_pendientes: int
    votos_blancos: int
    votos_nulos: int
    candidatos: List[CandidateResult]
    ganador: Optional[CandidateResult] = None
    fecha_cierre: Optional[datetime] = None

# --- DASHBOARD STATS ---
class DashboardStatsResponse(BaseModel):
    total_elecciones: int
    elecciones_activas: int
    total_padron: int
    total_votos_emitidos: int
    participacion_global: float
    ultimas_elecciones: List[ElectionResponse]

# --- AUDITORÍA ---
class AuditLogResponse(BaseModel):
    id: int
    fecha: datetime
    usuario: str
    accion: str
    detalle: Optional[str] = None
    prev_hash: Optional[str] = None
    record_hash: Optional[str] = None

    class Config:
        from_attributes = True


class AuditIntegrityCheckResponse(BaseModel):
    integro: bool
    total_revisados: int
    primer_hash: Optional[str] = None
    ultimo_hash: Optional[str] = None
    fallo_en_id: Optional[int] = None
    razon: Optional[str] = None
    fecha_verificacion: str


class AuditCheckpointResponse(BaseModel):
    success: bool
    timestamp: str
    total_records: int
    last_record_id: Optional[int] = None
    head_hash: str
    checkpoint_hash: str
    firmado_por: str
    instrucciones_anclaje: str
