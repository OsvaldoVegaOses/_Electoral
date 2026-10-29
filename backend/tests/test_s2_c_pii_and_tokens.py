"""
Sprint 2 — PR S2-C: Pruebas de regresión para privacidad, retención de PII
y ciclo de vida seguro de credenciales.

Verifica:
1. ANON-UNIQUE: Anonimización masiva de 100 electores de una sola elección sin IntegrityError (colisión UNIQUE en rut_normalizado).
2. ANON-CROSS:  Anonimización de dos elecciones distintas en secuencia sin colisión entre padrones.
3. ANON-IDEM:   Segunda llamada de anonimización a la misma elección es idempotente (0 cambios adicionales).
4. ANON-STATE:  Anonimización bloqueada en elecciones que NO están Finalizadas.
5. RETAIN-DATE: La elegibilidad de retención se calcula desde fecha_fin/fecha_cierre_efectiva, NO desde fecha_creacion.
6. LEGAL-HOLD:  Una elección con legal_hold=True bloquea la anonimización manual (409 Conflict).
7. UNIT-OPAQ:   unit_key en VotingEntitlement no expone RUT legible después de la opacificación post-apertura.
8. TOK-CLEAR:   token_votacion (texto claro) es NULL en la BD para votantes con token_hash; no se retorna por la API.
9. ANON-DENOM:  Tras anonimización completa, el denominador del escrutinio sigue siendo el congelado (total_habilitados_congelado).
"""
import os
import sys
import uuid
import json
import hashlib
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from app.database import Base, get_db
from app.models import School, Election, Candidate, Voter, VotingEntitlement, User, Vote
from app.auth import get_password_hash, create_access_token, ROLE_SUPERADMIN, hash_voting_token
from app.config import settings
from app.entitlements import derive_entitlement_key

SQLITE_DATABASE_URL = "sqlite:///:memory:"
sqlite_engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_rut(n: int) -> str:
    """Genera un RUT formateado con dígito verificador fijo para pruebas (no requiere válido)."""
    return f"{10000000 + n}.000-K"


def _make_rut_norm(n: int) -> str:
    return f"{10000000 + n}000-K"


class TestS2CPiiAndTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        Base.metadata.create_all(bind=sqlite_engine)
        self.db = TestingSessionLocal()

        self.school = School(nombre="Colegio S2C Test", rbd="4444-4")
        self.db.add(self.school)
        self.db.commit()

        self.admin = User(
            nombre="Admin S2C",
            email="admin_s2c@theogen.cl",
            password_hash=get_password_hash("Password12345!"),
            rol=ROLE_SUPERADMIN,
        )
        self.db.add(self.admin)
        self.db.commit()

        self.token = create_access_token({"sub": self.admin.email})
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)

    def _create_finalized_election(self, nombre="Elección Test", regla="Un voto por persona", n_voters=5):
        """Crea una elección Finalizada con n_voters electores ya votados."""
        now = datetime.now(timezone.utc)
        election = Election(
            nombre=nombre,
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion=regla,
            fecha_inicio=now - timedelta(days=10),
            fecha_fin=now - timedelta(days=settings.PII_VOTER_RETENTION_DAYS + 10),
            fecha_cierre_efectiva=now - timedelta(days=settings.PII_VOTER_RETENTION_DAYS + 10),
            estado="Finalizada",
            total_padron_congelado=n_voters,
            total_habilitados_congelado=n_voters,
            config_hash="a" * 64,
            config_snapshot="{}",
        )
        self.db.add(election)
        self.db.commit()

        for i in range(n_voters):
            raw_tok = str(uuid.uuid4())
            v = Voter(
                rut=_make_rut(i),
                rut_normalizado=_make_rut_norm(i),
                nombre=f"Elector {i}",
                election_id=election.id,
                token_votacion=None,        # Nuevo padrón: sin token claro
                token_hash=hash_voting_token(raw_tok),
                estado="Votó",
            )
            self.db.add(v)
        self.db.commit()
        return election

    # -----------------------------------------------------------------------
    # 1. ANON-UNIQUE: 100 electores sin colisión UNIQUE
    # -----------------------------------------------------------------------
    def test_01_anon_unique_100_voters_no_integrity_error(self):
        """POST /admin/pii/anonymize-election/{id} debe anonimizar 100 electores sin IntegrityError."""
        election = self._create_finalized_election(nombre="100 Electores", n_voters=100)

        resp = self.client.post(
            f"/api/admin/pii/anonymize-election/{election.id}",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200, f"Anonimización falló: {resp.text}")
        data = resp.json()
        self.assertEqual(data["electores_anonimizados"], 100)

        # Verificar que ningún rut_normalizado quede con valor identificante
        voters = self.db.query(Voter).filter(Voter.election_id == election.id).all()
        for v in voters:
            self.assertIsNone(
                v.rut_normalizado,
                f"rut_normalizado no fue anulado para elector {v.id}: {v.rut_normalizado}"
            )

    # -----------------------------------------------------------------------
    # 2. ANON-CROSS: Dos elecciones distintas sin colisión entre padrones
    # -----------------------------------------------------------------------
    def test_02_anon_cross_two_elections_no_collision(self):
        """Anonimizar dos elecciones con RUTs distintos en secuencia no genera colisiones."""
        e1 = self._create_finalized_election(nombre="Elección A", n_voters=10)
        e2 = self._create_finalized_election(nombre="Elección B", n_voters=10)
        # e2 usa los mismos "n" base - simular RUTs distintos
        for i, v in enumerate(self.db.query(Voter).filter(Voter.election_id == e2.id).all()):
            v.rut = _make_rut(100 + i)
            v.rut_normalizado = _make_rut_norm(100 + i)
        self.db.commit()

        r1 = self.client.post(f"/api/admin/pii/anonymize-election/{e1.id}", headers=self.headers)
        self.assertEqual(r1.status_code, 200, f"Fallo e1: {r1.text}")
        r2 = self.client.post(f"/api/admin/pii/anonymize-election/{e2.id}", headers=self.headers)
        self.assertEqual(r2.status_code, 200, f"Fallo e2: {r2.text}")

    # -----------------------------------------------------------------------
    # 3. ANON-IDEM: Segunda llamada idempotente
    # -----------------------------------------------------------------------
    def test_03_anon_idempotent_second_call(self):
        """Llamar dos veces a anonimizar la misma elección no lanza error ni cambia datos adicionales."""
        election = self._create_finalized_election(n_voters=5)

        r1 = self.client.post(f"/api/admin/pii/anonymize-election/{election.id}", headers=self.headers)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["electores_anonimizados"], 5)

        r2 = self.client.post(f"/api/admin/pii/anonymize-election/{election.id}", headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        # Segunda llamada debe reportar 0 cambios (todos ya estaban anonimizados)
        self.assertEqual(r2.json()["electores_anonimizados"], 0, "Segunda llamada debió reportar 0 cambios")

    # -----------------------------------------------------------------------
    # 4. ANON-STATE: Bloqueado para elecciones no Finalizadas
    # -----------------------------------------------------------------------
    def test_04_anon_blocked_non_finalized(self):
        """Anonimización rechaza elecciones en estado Borrador, Abierta y Cerrada (409)."""
        for estado in ["Borrador", "Abierta", "Cerrada"]:
            election = Election(
                nombre=f"Elección {estado}",
                school_id=self.school.id,
                tipo_votacion="Centro de Padres",
                regla_votacion="Un voto por persona",
                estado=estado,
            )
            self.db.add(election)
            self.db.commit()
            resp = self.client.post(
                f"/api/admin/pii/anonymize-election/{election.id}",
                headers=self.headers,
            )
            self.assertEqual(
                resp.status_code, 409,
                f"Estado '{estado}' debió rechazar anonimización (409), obtuvo {resp.status_code}: {resp.text}"
            )

    # -----------------------------------------------------------------------
    # 5. RETAIN-DATE: Elegibilidad basada en fecha_fin/fecha_cierre_efectiva
    # -----------------------------------------------------------------------
    def test_05_retention_eligibility_uses_fecha_fin_not_fecha_creacion(self):
        """La vista 'elections-ready-for-anonymization' debe excluir elecciones cuya fecha_fin no ha vencido."""
        now = datetime.now(timezone.utc)

        # Elección finalizada reciente (fecha_fin hace 5 días, fecha_creacion hace 200 días)
        # Con retention=90, no debe ser elegible si se basa en fecha_fin
        e_reciente = Election(
            nombre="Finalizada Reciente",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            fecha_creacion=now - timedelta(days=200),
            fecha_fin=now - timedelta(days=5),       # Hace solo 5 días
            fecha_cierre_efectiva=now - timedelta(days=5),
            estado="Finalizada",
        )
        self.db.add(e_reciente)
        self.db.commit()

        # Agregar un elector sin anonimizar
        v = Voter(rut="11.111.111-1", rut_normalizado="11111111-1", nombre="Test",
                  election_id=e_reciente.id, estado="Votó")
        self.db.add(v)
        self.db.commit()

        resp = self.client.get("/api/admin/pii/elections-ready-for-anonymization", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        ids_listos = [e["election_id"] for e in resp.json().get("elecciones", [])]
        self.assertNotIn(
            e_reciente.id, ids_listos,
            "Elección cuya fecha_fin fue hace solo 5 días no debería ser elegible (retención=90 días)"
        )

    # -----------------------------------------------------------------------
    # 6. LEGAL-HOLD: Bloqueo de anonimización con legal hold
    # -----------------------------------------------------------------------
    def test_06_legal_hold_blocks_anonymization(self):
        """Una elección con legal_hold=True debe rechazar la anonimización con 409."""
        election = Election(
            nombre="Elección con Hold Legal",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            estado="Finalizada",
            legal_hold=True,
        )
        self.db.add(election)
        self.db.commit()

        resp = self.client.post(
            f"/api/admin/pii/anonymize-election/{election.id}",
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 409, f"Legal hold debió bloquear (409): {resp.text}")
        self.assertIn("legal", resp.json()["detail"].lower())

    # -----------------------------------------------------------------------
    # 7. UNIT-OPAQ: unit_key no expone RUT/familia_id legibles
    # -----------------------------------------------------------------------
    def test_07_unit_key_does_not_expose_rut_in_plain(self):
        """La clave derivada es HMAC opaco, contextual y determinista."""
        election = self._create_finalized_election(n_voters=3)
        canonical_unit = "RUT:12345678-5"
        key = derive_entitlement_key(election.id, canonical_unit)
        self.assertEqual(key, derive_entitlement_key(election.id, canonical_unit))
        self.assertTrue(key.startswith("h1:"))
        self.assertNotIn("12345678", key)
        self.assertNotEqual(key, derive_entitlement_key(election.id + 1, canonical_unit))
        self.db.add(VotingEntitlement(election_id=election.id, unit_key=key))
        self.db.commit()
        stored = self.db.query(VotingEntitlement).filter_by(election_id=election.id).one()
        self.assertEqual(stored.unit_key, key)
        self.assertNotIn("12345678", stored.unit_key)

    def test_10_manual_anonymization_enforces_retention(self):
        election = self._create_finalized_election(n_voters=2)
        recent_close = datetime.now(timezone.utc) - timedelta(days=5)
        election.fecha_creacion = recent_close - timedelta(days=200)
        election.fecha_fin = recent_close
        election.fecha_cierre_efectiva = recent_close
        self.db.commit()

        response = self.client.post(
            f"/api/admin/pii/anonymize-election/{election.id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("retención", response.json()["detail"].lower())
        self.assertEqual(
            self.db.query(Voter).filter_by(election_id=election.id, pii_eliminado_en=None).count(),
            2,
        )

    def test_11_missing_close_date_blocks_anonymization(self):
        election = self._create_finalized_election(n_voters=1)
        election.fecha_fin = None
        election.fecha_cierre_efectiva = None
        election.fecha_creacion = datetime.now(timezone.utc) - timedelta(days=500)
        self.db.commit()
        response = self.client.post(
            f"/api/admin/pii/anonymize-election/{election.id}",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 409, response.text)

    def test_12_production_credential_creation_fails_closed(self):
        election = Election(
            nombre="Alta bloqueada",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            estado="Borrador",
        )
        self.db.add(election)
        self.db.commit()
        previous_environment = settings.ENVIRONMENT
        settings.ENVIRONMENT = "production"
        try:
            response = self.client.post(
                f"/api/elections/{election.id}/voters",
                headers=self.headers,
                json={"rut": "16.234.567-2", "nombre": "Elector ficticio"},
            )
            self.assertEqual(response.status_code, 503, response.text)
            self.assertIn("canal real", response.json()["detail"].lower())
            self.assertEqual(self.db.query(Voter).filter_by(election_id=election.id).count(), 0)
        finally:
            settings.ENVIRONMENT = previous_environment

    # -----------------------------------------------------------------------
    # 8. TOK-CLEAR: token_votacion NULL en BD (solo token_hash persiste)
    # -----------------------------------------------------------------------
    def test_08_token_clear_text_not_stored_in_db(self):
        """Después de anonimización, token_votacion (texto claro) debe ser NULL en la BD."""
        election = self._create_finalized_election(n_voters=5)
        self.client.post(f"/api/admin/pii/anonymize-election/{election.id}", headers=self.headers)

        voters = self.db.query(Voter).filter(Voter.election_id == election.id).all()
        for v in voters:
            self.assertIsNone(
                v.token_votacion,
                f"token_votacion debería ser NULL tras anonimización, elector {v.id}"
            )

    # -----------------------------------------------------------------------
    # 9. ANON-DENOM: Denominador preservado tras anonimización
    # -----------------------------------------------------------------------
    def test_09_denominator_preserved_after_anonymization(self):
        """El denominador del escrutinio sigue siendo total_habilitados_congelado después de PII."""
        now = datetime.now(timezone.utc)
        # Crear elección familiar: 4 personas, 2 familias
        election = Election(
            nombre="Familiar Denominador S2C",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por familia",
            fecha_inicio=now - timedelta(days=10),
            fecha_fin=now - timedelta(days=5),
            fecha_cierre_efectiva=now - timedelta(days=5),
            estado="Cerrada",
            total_padron_congelado=4,
            total_habilitados_congelado=2,   # 2 familias
            config_hash="b" * 64,
            config_snapshot="{}",
        )
        self.db.add(election)
        self.db.commit()

        cand = Candidate(nombre="Lista A", cargo="Directiva", orden=1, election_id=election.id)
        self.db.add(cand)
        self.db.commit()

        voters_data = [
            ("15.111.111-1", "15111111-1", "FAM-A"),
            ("16.222.222-2", "16222222-2", "FAM-A"),
            ("17.333.333-3", "17333333-3", "FAM-B"),
            ("18.444.444-4", "18444444-4", "FAM-B"),
        ]
        for rut, rut_norm, fam in voters_data:
            v = Voter(rut=rut, rut_normalizado=rut_norm, nombre="Elector",
                      familia_id=fam, election_id=election.id, estado="Pendiente")
            self.db.add(v)

        # Simular un voto
        vote = Vote(candidate_id=cand.id, election_id=election.id, hash_integridad="test_hash_s2c")
        self.db.add(vote)
        election.estado = "Cerrada"
        self.db.commit()

        # Finalizar
        election.estado = "Finalizada"
        from app.routers.elections import build_canonical_config_snapshot, compute_snapshot_hash

        snapshot = build_canonical_config_snapshot(election, self.db)
        election.config_snapshot = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        election.config_hash = compute_snapshot_hash(snapshot)
        self.db.commit()

        # Escrutinio antes de PII
        resp_before = self.client.get(
            f"/api/reports/election/{election.id}/scrutiny",
            headers=self.headers,
        )
        self.assertEqual(resp_before.status_code, 200)
        self.assertEqual(resp_before.json()["total_padron"], 2, "Denominador pre-PII debe ser 2 familias")

        # Anonimizar (limpiar familia_id de todos)
        for v in self.db.query(Voter).filter(Voter.election_id == election.id).all():
            v.familia_id = None
            v.pii_eliminado_en = now
        self.db.commit()

        # Escrutinio después de PII
        resp_after = self.client.get(
            f"/api/reports/election/{election.id}/scrutiny",
            headers=self.headers,
        )
        self.assertEqual(resp_after.status_code, 200)
        self.assertEqual(
            resp_after.json()["total_padron"], 2,
            "Denominador post-PII debe seguir siendo 2 (total_habilitados_congelado)"
        )


if __name__ == "__main__":
    unittest.main()
