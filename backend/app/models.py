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
    motor = Column(String(16), nullable=False, default="mvp", server_default="mvp")
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
    # S2-B: Congelamiento e instantánea íntegra
    fecha_cierre_efectiva = Column(DateTime(timezone=True), nullable=True)
    total_padron_congelado = Column(Integer, nullable=True)
    total_habilitados_congelado = Column(Integer, nullable=True)
    config_snapshot = Column(Text, nullable=True)
    # S2-C: Retención legal — bloquea anonimización y purga mientras sea True
    legal_hold = Column(Boolean, default=False, nullable=False)
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
        # S2-C: La restricción de unicidad permite NULL en rut_normalizado (post-anonimización)
        # SQLite/PostgreSQL: múltiples NULLs no colisionan en UNIQUE — comportamiento estándar SQL
        UniqueConstraint("election_id", "rut_normalizado", name="uq_election_voter_rut"),
    )

class VotingEntitlement(Base):
    """
    A4 - P0: Entidad de derecho a sufragio / unidad electoral única.
    Garantiza unicidad estricta de voto a nivel de base de datos.
    unit_key contiene un HMAC contextual, no el RUT ni el identificador familiar.
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

class AuditChainHead(Base):
    __tablename__ = "audit_chain_heads"

    id = Column(Integer, primary_key=True)
    head_hash = Column(String(64), nullable=False)
    last_log_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


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


class BeleniosBinding(Base):
    __tablename__ = "belenios_bindings"
    id = Column(Integer, primary_key=True)
    election_id = Column(Integer, ForeignKey("elections.id"), nullable=False, unique=True)
    reference = Column(String(32), nullable=False, unique=True)
    policy = Column(String(2), nullable=False)
    remote_uuid = Column(String(14), nullable=True)
    phase = Column(String(32), nullable=False, default="PREPARING")
    inflight = Column(String(36), nullable=True)
    draft_json = Column(Text, nullable=False)
    approval_ref = Column(String(100), nullable=False)
    total_people = Column(Integer, nullable=False)
    total_units = Column(Integer, nullable=False)
    verified_result = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("policy", "remote_uuid", name="uq_belenios_remote"),)


class BeleniosUnit(Base):
    __tablename__ = "belenios_units"
    id = Column(Integer, primary_key=True)
    binding_id = Column(Integer, ForeignKey("belenios_bindings.id"), nullable=False, index=True)
    representative_id = Column(Integer, ForeignKey("voters.id"), nullable=False)
    alias = Column(String(80), nullable=False)
    __table_args__ = (UniqueConstraint("binding_id", "representative_id", name="uq_belenios_representative"),
                      UniqueConstraint("binding_id", "alias", name="uq_belenios_alias"))


class BeleniosOperation(Base):
    __tablename__ = "belenios_operations"
    id = Column(String(36), primary_key=True)
    binding_id = Column(Integer, ForeignKey("belenios_bindings.id"), nullable=False, index=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String(32), nullable=False)
    phase = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CredentialDelivery(Base):
    __tablename__ = "credential_deliveries"
    id = Column(String(36), primary_key=True)
    voter_id = Column(Integer, ForeignKey("voters.id"), nullable=False, index=True)
    previous_hash = Column(String(128), nullable=True)
    proposed_hash = Column(String(128), nullable=False)
    status = Column(String(24), nullable=False)
    message_id = Column(String(255), nullable=True)
    active_slot = Column(String(50), unique=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

