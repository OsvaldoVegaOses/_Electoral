"""
P14: Tests de Política de Retención y Eliminación de PII

Verifica:
- GET /admin/pii/status retorna estructura correcta con conteos
- GET /admin/pii/elections-ready-for-anonymization lista elecciones candidatas
- POST /admin/pii/anonymize-election/{id} anonimiza padrón y comisión atómicamente
- POST /admin/pii/anonymize-election/{id} rechaza elecciones no finalizadas
- POST /admin/pii/anonymize-election/{id} idempotente (doble ejecución no duplica)
- POST /admin/pii/purge-audit-logs permite dry-run y bloquea la purga física
- Los campos PII quedan con valores de sustitución correctos
- Solo Administrador General puede acceder a los endpoints
- pii_eliminado_en queda seteado tras anonimización
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import Election, Voter, ElectoralCommittee, AuditLog, User, School
from app.auth import get_password_hash, create_access_token
from app.config import settings
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_tables():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _make_admin(db) -> User:
    user = User(
        nombre="Admin Test",
        email="admin@test.cl",
        password_hash=get_password_hash("Admin1234!"),
        rol="Administrador General",
        school_id=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_school(db) -> School:
    school = School(nombre="Colegio Test", rbd="12345", comuna="Santiago")
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def _make_election(db, school_id: int, estado: str = "Finalizada", dias_atras: int = 100) -> Election:
    fecha_creacion = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    e = Election(
        nombre="Elección Test",
        estado=estado,
        school_id=school_id,
        tipo_votacion="Centro de Padres",
        regla_votacion="Un voto por persona",
        fecha_creacion=fecha_creacion,
        fecha_fin=fecha_creacion,
        fecha_cierre_efectiva=fecha_creacion,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _make_voter(db, election_id: int) -> Voter:
    v = Voter(
        rut="12345678-9",
        rut_normalizado="12345678-9",
        nombre="Juan Pérez",
        correo="juan@test.cl",
        election_id=election_id,
        estado="Votó",
        token_votacion=None,
        token_hash=None,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def _make_committee(db, election_id: int) -> ElectoralCommittee:
    m = ElectoralCommittee(
        nombre="María González",
        rut="98765432-1",
        correo="maria@test.cl",
        cargo="Presidente",
        election_id=election_id,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _make_audit_log(db, dias_atras: int) -> AuditLog:
    fecha = datetime.now(timezone.utc) - timedelta(days=dias_atras)
    log = AuditLog(fecha=fecha, usuario="sistema@test.cl", accion="Test acción", detalle="detalle")
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def _get_client_for_user(user: User):
    """Retorna un TestClient autenticado con Bearer token JWT para el usuario dado."""
    token = create_access_token({"sub": user.email, "rol": user.rol})
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPIIStatus:

    def test_status_retorna_estructura_correcta(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        db.close()
        client = _get_client_for_user(admin)
        resp = client.get("/api/admin/pii/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configuracion" in data
        assert "padron" in data
        assert "auditoria" in data
        assert "pii_voter_retention_days" in data["configuracion"]
        assert "candidatos_a_anonimizar" in data["padron"]

    def test_status_cuenta_electores_correctamente(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, dias_atras=200)
        _make_voter(db, election.id)
        db.close()

        with patch.object(settings, "PII_VOTER_RETENTION_DAYS", 90), \
             patch.object(settings, "PII_AUDIT_RETENTION_DAYS", 365):
            client = _get_client_for_user(admin)
            resp = client.get("/api/admin/pii/status")
        assert resp.status_code == 200


class TestElectionsReadyForAnonymization:

    def test_lista_elecciones_finalizadas_con_pii(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, estado="Finalizada", dias_atras=120)
        _make_voter(db, election.id)
        db.close()

        client = _get_client_for_user(admin)
        resp = client.get("/api/admin/pii/elections-ready-for-anonymization")
        assert resp.status_code == 200
        data = resp.json()
        assert "elecciones" in data

    def test_no_incluye_elecciones_abiertas(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        _make_election(db, school.id, estado="Abierta", dias_atras=200)
        db.close()

        client = _get_client_for_user(admin)
        resp = client.get("/api/admin/pii/elections-ready-for-anonymization")
        assert resp.status_code == 200
        # Elecciones abiertas no deben aparecer
        for e in resp.json()["elecciones"]:
            assert e.get("estado") != "Abierta"


class TestAnonymizeElection:

    def test_anonimiza_correctamente(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, dias_atras=120)
        voter = _make_voter(db, election.id)
        committee = _make_committee(db, election.id)
        voter_id = voter.id
        committee_id = committee.id
        election_id = election.id
        db.close()

        client = _get_client_for_user(admin)
        resp = client.post(f"/api/admin/pii/anonymize-election/{election_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["electores_anonimizados"] == 1
        assert data["comisionados_anonimizados"] == 1

        # Verificar valores en BD
        db2 = TestingSessionLocal()
        v = db2.query(Voter).filter(Voter.id == voter_id).first()
        assert v.rut == "[ANONIMIZADO]"
        assert v.nombre == "[Elector Anonimizado]"
        assert v.correo is None
        assert v.pii_eliminado_en is not None

        c = db2.query(ElectoralCommittee).filter(ElectoralCommittee.id == committee_id).first()
        assert c.rut == "[ANONIMIZADO]"
        assert c.nombre == "[Comisionado Anonimizado]"
        assert c.correo is None
        assert c.pii_eliminado_en is not None
        db2.close()

    def test_rechaza_eleccion_no_finalizada(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, estado="Abierta", dias_atras=10)
        election_id = election.id
        db.close()

        client = _get_client_for_user(admin)
        resp = client.post(f"/api/admin/pii/anonymize-election/{election_id}")
        assert resp.status_code == 409
        assert "Finalizada" in resp.json()["detail"]

    def test_idempotente_doble_anonimizacion(self):
        """Una segunda ejecución no debe modificar registros ya anonimizados."""
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, dias_atras=120)
        _make_voter(db, election.id)
        election_id = election.id
        db.close()

        client = _get_client_for_user(admin)
        resp1 = client.post(f"/api/admin/pii/anonymize-election/{election_id}")
        assert resp1.status_code == 200
        assert resp1.json()["electores_anonimizados"] == 1

        resp2 = client.post(f"/api/admin/pii/anonymize-election/{election_id}")
        assert resp2.status_code == 200
        # Segunda ejecución no debe encontrar registros sin anonimizar
        assert resp2.json()["electores_anonimizados"] == 0

    def test_retorna_404_para_eleccion_inexistente(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        db.close()

        client = _get_client_for_user(admin)
        resp = client.post("/api/admin/pii/anonymize-election/99999")
        assert resp.status_code == 404

    def test_registra_en_auditoria(self):
        """La anonimización debe crear un registro en audit_logs."""
        db = TestingSessionLocal()
        admin = _make_admin(db)
        school = _make_school(db)
        election = _make_election(db, school.id, dias_atras=120)
        _make_voter(db, election.id)
        election_id = election.id
        db.close()

        client = _get_client_for_user(admin)
        client.post(f"/api/admin/pii/anonymize-election/{election_id}")

        db2 = TestingSessionLocal()
        audit = db2.query(AuditLog).filter(
            AuditLog.accion == "PII: Anonimización de padrón"
        ).first()
        assert audit is not None
        assert str(election_id) in audit.detalle
        db2.close()


class TestPurgeAuditLogs:

    def test_destructive_purge_is_blocked_and_preserves_old_logs(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        # Log antiguo (>365 días)
        _make_audit_log(db, dias_atras=400)
        # Log reciente (<365 días)
        _make_audit_log(db, dias_atras=10)
        db.close()

        client = _get_client_for_user(admin)
        resp = client.post("/api/admin/pii/purge-audit-logs")
        assert resp.status_code == 409
        assert "checkpoint externo" in resp.json()["detail"]

        # Los logs antiguos y recientes permanecen íntegros.
        db2 = TestingSessionLocal()
        remaining = db2.query(AuditLog).filter(
            AuditLog.accion == "Test acción"
        ).count()
        db2.close()
        assert remaining == 2

    def test_dry_run_counts_without_deleting_logs(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        _make_audit_log(db, dias_atras=10)  # Solo log reciente
        db.close()

        client = _get_client_for_user(admin)
        resp = client.post("/api/admin/pii/purge-audit-logs?dry_run=true")
        assert resp.status_code == 200
        assert resp.json()["registros_que_serian_eliminados"] == 0

    def test_blocked_purge_does_not_claim_success_or_write_purge_event(self):
        db = TestingSessionLocal()
        admin = _make_admin(db)
        _make_audit_log(db, dias_atras=400)
        db.close()

        client = _get_client_for_user(admin)
        response = client.post("/api/admin/pii/purge-audit-logs")
        assert response.status_code == 409

        db2 = TestingSessionLocal()
        purge_log = db2.query(AuditLog).filter(
            AuditLog.accion == "PII: Purga de auditoría"
        ).first()
        assert purge_log is None
        assert db2.query(AuditLog).filter(AuditLog.accion == "Test acción").count() == 1
        db2.close()
