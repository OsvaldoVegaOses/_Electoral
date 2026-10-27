from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.database import Base


def _utcnow():
    """HIGH-01: Helper timezone-aware para defaults de columnas SQLAlchemy"""
    return datetime.now(timezone.utc)

class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    rbd = Column(String(50), nullable=True, index=True)
    comuna = Column(String(100), nullable=True)
    correo_contacto = Column(String(150), nullable=True)
    telefono = Column(String(50), nullable=True)
    logo = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime, default=_utcnow)

    # Relaciones
    elections = relationship("Election", back_populates="school", cascade="all, delete-orphan")

class Election(Base):
    __tablename__ = "elections"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_inicio = Column(DateTime(timezone=True), nullable=True)
    fecha_fin = Column(DateTime(timezone=True), nullable=True)
    # Estados: Borrador, Abierta, Cerrada, Finalizada
    estado = Column(String(50), default="Borrador", index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=False)
    # Tipos: Centro de Padres, Centro de Alumnos, Consejo Escolar, Consulta Ciudadana, Directiva Organización
    tipo_votacion = Column(String(100), nullable=False, default="Centro de Padres")
    # Regla: "Un voto por persona" o "Un voto por familia"
    regla_votacion = Column(String(50), nullable=False, default="Un voto por persona")
    config_hash = Column(String(128), nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=_utcnow)

    # Relaciones
    school = relationship("School", back_populates="elections")
    committee_members = relationship("ElectoralCommittee", back_populates="election", cascade="all, delete-orphan")
    voters = relationship("Voter", back_populates="election", cascade="all, delete-orphan")
    candidates = relationship("Candidate", back_populates="election", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="election", cascade="all, delete-orphan")
    entitlements = relationship("VotingEntitlement", back_populates="election", cascade="all, delete-orphan")

class ElectoralCommittee(Base):
    __tablename__ = "electoral_committees"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    rut = Column(String(50), nullable=False)
    correo = Column(String(150), nullable=True)
    cargo = Column(String(100), nullable=False)  # Presidente, Secretario, Vocal
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    # P14: Marca de tiempo de anonimización de PII (NULL = datos aún vigentes)
    pii_eliminado_en = Column(DateTime(timezone=True), nullable=True, index=True)

    election = relationship("Election", back_populates="committee_members")

class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, index=True)
    rut = Column(String(50), nullable=False, index=True)
    rut_normalizado = Column(String(50), nullable=True, index=True)
    nombre = Column(String(200), nullable=False)
    curso = Column(String(100), nullable=True)
    correo = Column(String(150), nullable=True)
    familia_id = Column(String(100), nullable=True, index=True)
    token_votacion = Column(String(100), unique=True, index=True, nullable=True)
    # P8: Derivación/hash resistente para canje seguro de credenciales (HMAC-SHA256)
    token_hash = Column(String(128), unique=True, index=True, nullable=True)
    # Estados: Pendiente, Votó, Bloqueado
    estado = Column(String(50), default="Pendiente", index=True)
    fecha_voto = Column(DateTime(timezone=True), nullable=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    # P14: Marca de tiempo de anonimización de PII (NULL = datos aún vigentes)
    pii_eliminado_en = Column(DateTime(timezone=True), nullable=True, index=True)

    election = relationship("Election", back_populates="voters")

    __table_args__ = (
        UniqueConstraint("election_id", "rut_normalizado", name="uq_election_voter_rut"),
    )

class VotingEntitlement(Base):
    """
    A4 - P0: Entidad de derecho a sufragio / unidad electoral única.
    Garantiza unicidad estricta de voto a nivel de base de datos.
    Para 'Un voto por persona': unit_key = 'RUT:<rut_normalizado>'
    Para 'Un voto por familia': unit_key = 'FAM:<familia_id>'
    """
    __tablename__ = "voting_entitlements"

    id = Column(Integer, primary_key=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False, index=True)
    unit_key = Column(String(100), nullable=False, index=True)
    # Estados: Pendiente, Consumido, Bloqueado
    estado = Column(String(50), default="Pendiente", index=True, nullable=False)
    fecha_consumo = Column(DateTime(timezone=True), nullable=True)
    voter_id_consumidor = Column(Integer, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), default=_utcnow)

    election = relationship("Election", back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("election_id", "unit_key", name="uq_election_unit_key"),
    )


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(200), nullable=False)
    cargo = Column(String(100), nullable=True)
    descripcion = Column(Text, nullable=True)
    foto = Column(Text, nullable=True)
    orden = Column(Integer, default=0)
    es_blanco = Column(Boolean, default=False)
    es_nulo = Column(Boolean, default=False)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)

    election = relationship("Election", back_populates="candidates")
    votes = relationship("Vote", back_populates="candidate")

class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    voter_id = Column(Integer, nullable=True)  # Registro referencial para no duplicar
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False)
    fecha_voto = Column(DateTime(timezone=True), default=_utcnow)
    hash_integridad = Column(String(128), nullable=False, unique=True, index=True)

    election = relationship("Election", back_populates="votes")
    candidate = relationship("Candidate", back_populates="votes")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime(timezone=True), default=_utcnow, index=True)
    usuario = Column(String(150), default="Sistema")
    accion = Column(String(150), nullable=False, index=True)
    detalle = Column(Text, nullable=True)
    school_id = Column(Integer, nullable=True, index=True)
    # P15: Encadenamiento criptográfico para bitácora append-only verificable
    prev_hash = Column(String(64), nullable=True)
    record_hash = Column(String(64), nullable=True, index=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Roles: "Administrador General", "Responsable Institucional", "Comisión Electoral"
    rol = Column(String(50), default="Administrador General")
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True, index=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=True, index=True)
    fecha_creacion = Column(DateTime(timezone=True), default=_utcnow)

    # Relaciones de ámbito organizacional
    school = relationship("School")
    election = relationship("Election")

