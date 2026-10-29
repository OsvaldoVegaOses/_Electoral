"""
P15: Tests de Bitácora Append-Only y Encadenamiento Criptográfico Verificable

Verifica:
- El primer registro de auditoría tiene prev_hash == GENESIS_HASH.
- Cada registro sucesivo encadena su prev_hash al record_hash del registro anterior.
- Multiples log_audit(..., commit=False) en una misma transacción encadenan correctamente.
- verify_audit_log_chain() retorna integro=True para cadenas no adulteradas.
- La modificación directa de un campo (accion, detalle, usuario, fecha) rompe la verificación.
- La eliminación de un registro intermedio rompe el encadenamiento prev_hash.
- GET /api/audit/verify-integrity retorna reporte de integridad para Administrador General.
- GET /api/audit/verify-integrity deniega acceso (403) a roles sin privilegios globales.
- POST /api/audit/checkpoint genera digest de anclaje externo y registra el evento.
- POST /api/audit/checkpoint deniega acceso a usuarios no autorizados.
- GET /api/audit/logs incluye prev_hash y record_hash en su respuesta.
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import AuditLog, User, School
from app.auth import (
    get_password_hash,
    create_access_token,
    log_audit,
    compute_audit_hash,
    verify_audit_log_chain,
    GENESIS_HASH,
)
from main import app

# ---------------------------------------------------------------------------
# Setup: SQLite en memoria con StaticPool
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_tables():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_user(db, email="admin@test.cl", rol="Administrador General", school_id=None) -> User:
    u = User(
        nombre="Test User",
        email=email,
        password_hash=get_password_hash("Pass1234!"),
        rol=rol,
        school_id=school_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _client_for(user: User) -> TestClient:
    token = create_access_token({"sub": user.email, "rol": user.rol})
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ---------------------------------------------------------------------------
# Tests: Encadenamiento Criptográfico Unitario
# ---------------------------------------------------------------------------

class TestCryptographicHashChaining:

    def test_genesis_record_has_genesis_prev_hash(self):
        db = TestingSessionLocal()
        log = log_audit(db, accion="Inicio de Sistema", detalle="Primer registro", usuario="admin@theogen.cl")
        assert log is not None
        assert log.prev_hash == GENESIS_HASH
        assert log.record_hash is not None
        assert len(log.record_hash) == 64
        # Verificar que el hash coincide con el cálculo canónico
        expected = compute_audit_hash(GENESIS_HASH, log.fecha, log.usuario, log.accion, log.detalle, log.school_id)
        assert log.record_hash == expected
        db.close()

    def test_subsequent_record_chains_to_previous_hash(self):
        db = TestingSessionLocal()
        log1 = log_audit(db, accion="Acción 1", detalle="Detalle 1", usuario="user1@theogen.cl")
        log2 = log_audit(db, accion="Acción 2", detalle="Detalle 2", usuario="user2@theogen.cl")
        log3 = log_audit(db, accion="Acción 3", detalle="Detalle 3", usuario="user3@theogen.cl")

        assert log2.prev_hash == log1.record_hash
        assert log3.prev_hash == log2.record_hash
        db.close()

    def test_atomic_audit_with_commit_false_chains_correctly(self):
        """Múltiples registros en una misma transacción (commit=False) deben encadenar sin solaparse."""
        db = TestingSessionLocal()
        l1 = log_audit(db, accion="Paso 1", detalle="A", commit=False)
        l2 = log_audit(db, accion="Paso 2", detalle="B", commit=False)
        l3 = log_audit(db, accion="Paso 3", detalle="C", commit=False)
        db.commit()

        assert l2.prev_hash == l1.record_hash
        assert l3.prev_hash == l2.record_hash
        db.close()


# ---------------------------------------------------------------------------
# Tests: Algoritmo de Verificación de Integridad
# ---------------------------------------------------------------------------

class TestAuditIntegrityVerification:

    def test_verify_returns_integro_true_on_untampered_chain(self):
        db = TestingSessionLocal()
        for i in range(5):
            log_audit(db, accion=f"Evento {i}", detalle=f"Detalle {i}")
        result = verify_audit_log_chain(db)
        assert result["integro"] is True
        assert result["total_revisados"] == 5
        assert result["fallo_en_id"] is None
        db.close()

    def test_empty_audit_returns_integro_true(self):
        db = TestingSessionLocal()
        result = verify_audit_log_chain(db)
        assert result["integro"] is True
        assert result["total_revisados"] == 0
        db.close()

    def test_legacy_record_without_hash_is_not_declared_integral(self):
        db = TestingSessionLocal()
        legacy = AuditLog(accion="Evento legacy sin hash")
        db.add(legacy)
        db.commit()

        result = verify_audit_log_chain(db)

        assert result["integro"] is False
        assert result["fallo_en_id"] == legacy.id
        assert "legacy sin hash" in result["razon"]
        db.close()

    def test_first_record_must_use_genesis_hash(self):
        db = TestingSessionLocal()
        log = log_audit(db, accion="Genesis alterada")
        log.prev_hash = "a" * 64
        log.record_hash = compute_audit_hash(
            log.prev_hash, log.fecha, log.usuario, log.accion, log.detalle, log.school_id
        )
        db.commit()

        result = verify_audit_log_chain(db)

        assert result["integro"] is False
        assert result["fallo_en_id"] == log.id
        assert "Eslabón roto" in result["razon"]
        db.close()

    def test_tamper_detection_modifying_record_action_fails(self):
        db = TestingSessionLocal()
        for i in range(4):
            log_audit(db, accion=f"Evento {i}", detalle=f"Detalle {i}")

        # Simular ataque: alteración maliciosa de un registro en la base de datos
        tampered_log = db.query(AuditLog).filter(AuditLog.accion == "Evento 2").first()
        tampered_id = tampered_log.id
        tampered_log.accion = "Evento 2 ALTERADO"
        db.commit()

        result = verify_audit_log_chain(db)
        assert result["integro"] is False
        assert result["fallo_en_id"] == tampered_id
        assert "Contenido alterado" in result["razon"]
        db.close()

    def test_tamper_detection_modifying_record_detail_fails(self):
        db = TestingSessionLocal()
        for i in range(3):
            log_audit(db, accion=f"Accion {i}", detalle=f"Original {i}")

        target = db.query(AuditLog).filter(AuditLog.accion == "Accion 1").first()
        target_id = target.id
        target.detalle = "Detalle Modificado Fraudulentamente"
        db.commit()

        result = verify_audit_log_chain(db)
        assert result["integro"] is False
        assert result["fallo_en_id"] == target_id
        db.close()

    def test_tamper_detection_deleting_record_in_middle_fails(self):
        """Si un atacante elimina un registro, el eslabón prev_hash del siguiente queda roto."""
        db = TestingSessionLocal()
        l1 = log_audit(db, accion="A1")
        l2 = log_audit(db, accion="A2")
        l3 = log_audit(db, accion="A3")
        l3_id = l3.id

        # Eliminar el registro intermedio
        db.delete(l2)
        db.commit()

        result = verify_audit_log_chain(db)
        assert result["integro"] is False
        assert result["fallo_en_id"] == l3_id
        assert "Eslabón roto" in result["razon"]
        db.close()


# ---------------------------------------------------------------------------
# Tests: Endpoints de Verificación y Anclaje
# ---------------------------------------------------------------------------

class TestAuditEndpointsP15:

    def test_endpoint_verify_integrity_as_admin(self):
        db = TestingSessionLocal()
        admin = _make_user(db, email="superadmin@theogen.cl", rol="Administrador General")
        log_audit(db, accion="Prueba Endpoint 1", usuario=admin.email)
        log_audit(db, accion="Prueba Endpoint 2", usuario=admin.email)
        db.close()

        client = _client_for(admin)
        resp = client.get("/api/audit/verify-integrity")
        assert resp.status_code == 200
        data = resp.json()
        assert data["integro"] is True
        assert data["total_revisados"] >= 2
        assert data["ultimo_hash"] is not None

    def test_endpoint_verify_integrity_forbidden_for_non_admin(self):
        db = TestingSessionLocal()
        user = _make_user(db, email="comision@theogen.cl", rol="Comisión Electoral")
        db.close()

        client = _client_for(user)
        resp = client.get("/api/audit/verify-integrity")
        assert resp.status_code == 403

    def test_endpoint_checkpoint_generates_anchor(self):
        db = TestingSessionLocal()
        admin = _make_user(db, email="superadmin@theogen.cl", rol="Administrador General")
        log_audit(db, accion="Setup Elección", usuario=admin.email)
        db.close()

        client = _client_for(admin)
        resp = client.post("/api/audit/checkpoint")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "checkpoint_hash" in data
        assert len(data["checkpoint_hash"]) == 64
        assert data["head_hash"] is not None
        assert data["firmado_por"] == admin.email
        assert data["anchorage_status"] == "PENDIENTE_ANCLAJE_EXTERNO"
        assert data["independent_custody_confirmed"] is False
        assert data["artifact"]["digest_sha256"] == data["checkpoint_hash"]

        # El checkpoint debe haber registrado un evento en la propia bitácora
        db2 = TestingSessionLocal()
        checkpoint_audit = db2.query(AuditLog).filter(
            AuditLog.accion == "AUDIT: Generación de anclaje de bitácora"
        ).first()
        assert checkpoint_audit is not None
        assert data["checkpoint_hash"] in checkpoint_audit.detalle
        db2.close()

    def test_external_checkpoint_artifact_can_be_verified_and_tampering_is_rejected(self):
        db = TestingSessionLocal()
        admin = _make_user(db, email="checkpoint@test.cl", rol="Administrador General")
        log_audit(db, accion="Synthetic checkpoint event", usuario=admin.email)
        db.close()

        client = _client_for(admin)
        checkpoint_response = client.post("/api/audit/checkpoint")
        assert checkpoint_response.status_code == 200
        artifact = checkpoint_response.json()["artifact"]

        valid = client.post("/api/audit/checkpoint/verify", json=artifact)
        assert valid.status_code == 200
        assert valid.json()["integro"] is True

        artifact["total_records"] += 1
        altered = client.post("/api/audit/checkpoint/verify", json=artifact)
        assert altered.status_code == 200
        assert altered.json()["integro"] is False

    def test_endpoint_checkpoint_forbidden_for_non_admin(self):
        db = TestingSessionLocal()
        user = _make_user(db, email="responsable@theogen.cl", rol="Responsable Institucional")
        db.close()

        client = _client_for(user)
        resp = client.post("/api/audit/checkpoint")
        assert resp.status_code == 403

    def test_audit_logs_listing_includes_prev_hash_and_record_hash(self):
        db = TestingSessionLocal()
        admin = _make_user(db, email="superadmin@theogen.cl", rol="Administrador General")
        log_audit(db, accion="Evento Listable", detalle="Detalle Listable", usuario=admin.email)
        db.close()

        client = _client_for(admin)
        resp = client.get("/api/audit/logs")
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) >= 1
        first = logs[0]
        assert "prev_hash" in first
        assert "record_hash" in first
        assert first["record_hash"] is not None
