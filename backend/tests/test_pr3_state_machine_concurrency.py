import os
import sys
import unittest
import concurrent.futures
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.database import Base, get_db
from app.models import User, School, Election, Candidate, Voter, VotingEntitlement, Vote, ElectoralCommittee
from app.auth import get_password_hash, create_access_token, _failed_attempts
from app.entitlements import derive_entitlement_key

# In-memory SQLite for functional/state-machine testing
SQLITE_DATABASE_URL = "sqlite:///:memory:"
sqlite_engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLiteSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)


def override_get_db_sqlite():
    db = SQLiteSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestPR3StateMachineAndFreezing(unittest.TestCase):
    """
    Pruebas B1 & A4: Máquina de estados formal, validaciones de apertura,
    congelamiento de padrón/candidaturas y ventanas de tiempo UTC.
    """
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db_sqlite
        Base.metadata.create_all(bind=sqlite_engine)
        self.db = SQLiteSessionLocal()
        _failed_attempts.clear()

        # Colegio y usuarios
        self.school = School(nombre="Colegio San Ignacio", rbd="12345-6", comuna="Santiago")
        self.db.add(self.school)
        self.db.flush()

        self.admin = User(
            email="admin@test.cl",
            nombre="Admin General",
            password_hash=get_password_hash("Admin123!"),
            rol="Administrador General"
        )
        self.db.add(self.admin)
        self.db.commit()

        self.token_admin = create_access_token(data={"sub": self.admin.email, "rol": self.admin.rol})
        self.headers_admin = {"Authorization": f"Bearer {self.token_admin}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)
        app.dependency_overrides.clear()

    def test_cannot_open_without_voters(self):
        """No se puede abrir una elección sin electores en el padrón"""
        elec = Election(nombre="Elección Vacía", school_id=self.school.id, estado="Borrador")
        self.db.add(elec)
        self.db.commit()

        resp = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("padrón electoral vacío", resp.json()["detail"])

    def test_cannot_open_family_rule_with_missing_family_id(self):
        """En regla familiar, no se puede abrir si algún elector carece de familia_id"""
        elec = Election(
            nombre="Elección Familiar",
            school_id=self.school.id,
            estado="Borrador",
            regla_votacion="Un voto por familia"
        )
        self.db.add(elec)
        self.db.flush()

        voter = Voter(
            election_id=elec.id,
            rut="11.111.111-1",
            rut_normalizado="111111111",
            nombre="Juan Perez",
            familia_id=None,
            estado="Pendiente"
        )
        self.db.add(voter)
        self.db.commit()

        resp = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("familia_id", resp.json()["detail"])

    def test_cannot_open_without_regular_candidates(self):
        """No se puede abrir una elección sin al menos un candidato de lista regular"""
        elec = Election(
            nombre="Elección Sin Candidatos",
            school_id=self.school.id,
            estado="Borrador"
        )
        self.db.add(elec)
        self.db.flush()

        voter = Voter(
            election_id=elec.id,
            rut="11.111.111-1",
            rut_normalizado="111111111",
            nombre="Juan Perez",
            estado="Pendiente"
        )
        # Solo votos blanco y nulo por defecto
        c_blanco = Candidate(election_id=elec.id, nombre="Voto Blanco", es_blanco=True)
        c_nulo = Candidate(election_id=elec.id, nombre="Voto Nulo", es_nulo=True)
        self.db.add_all([voter, c_blanco, c_nulo])
        self.db.commit()

        resp = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("candidato o lista inscrita", resp.json()["detail"])

    def test_cannot_open_with_incoherent_dates(self):
        """No se puede abrir si fecha_inicio es posterior a fecha_fin"""
        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Fechas Malas",
            school_id=self.school.id,
            estado="Borrador",
            fecha_inicio=now + timedelta(days=2),
            fecha_fin=now + timedelta(days=1)
        )
        self.db.add(elec)
        self.db.flush()

        voter = Voter(
            election_id=elec.id,
            rut="11.111.111-1",
            rut_normalizado="111111111",
            nombre="Juan Perez",
            estado="Pendiente"
        )
        cand = Candidate(election_id=elec.id, nombre="Lista A", es_blanco=False, es_nulo=False)
        self.db.add_all([voter, cand])
        self.db.commit()

        resp = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Fechas incoherentes", resp.json()["detail"])

    def test_successful_open_provisions_entitlements_and_hash(self):
        """Apertura exitosa genera config_hash y provisiona VotingEntitlement"""
        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Valida",
            school_id=self.school.id,
            estado="Borrador",
            regla_votacion="Un voto por persona",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(hours=2)
        )
        self.db.add(elec)
        self.db.flush()

        v1 = Voter(
            election_id=elec.id,
            rut="11.111.111-1",
            rut_normalizado="111111111",
            nombre="Juan Perez",
            estado="Pendiente"
        )
        v2 = Voter(
            election_id=elec.id,
            rut="22.222.222-2",
            rut_normalizado="222222222",
            nombre="Maria Lopez",
            estado="Pendiente"
        )
        cand = Candidate(election_id=elec.id, nombre="Lista A", es_blanco=False, es_nulo=False)
        self.db.add_all([v1, v2, cand])
        self.db.commit()

        resp = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["estado"], "Abierta")
        self.assertTrue(len(data["config_hash"]) > 20)

        # Verificar que se crearon los VotingEntitlements
        entitlements = self.db.query(VotingEntitlement).filter(VotingEntitlement.election_id == elec.id).all()
        self.assertEqual(len(entitlements), 2)
        keys = {e.unit_key for e in entitlements}
        self.assertEqual(
            keys,
            {
                derive_entitlement_key(elec.id, "RUT:111111111"),
                derive_entitlement_key(elec.id, "RUT:222222222"),
            },
        )
        self.assertTrue(all(key.startswith("h1:") for key in keys))

    def test_put_election_cannot_change_estado_or_structural_fields(self):
        """PUT /api/elections/{id} no permite cambiar estado ni alterar campos estructurales si está abierta"""
        elec = Election(
            nombre="Elección Inmutable",
            school_id=self.school.id,
            estado="Borrador",
            regla_votacion="Un voto por persona"
        )
        self.db.add(elec)
        self.db.commit()

        # Intentar cambiar estado por PUT directo debe ser rechazado
        resp = self.client.put(
            f"/api/elections/{elec.id}",
            json={"estado": "Abierta"},
            headers=self.headers_admin
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("no puede modificarse mediante actualización general", resp.json()["detail"])

        # Abrir la elección formalmente
        v1 = Voter(election_id=elec.id, rut="11.111.111-1", rut_normalizado="111111111", nombre="Elector 1")
        cand = Candidate(election_id=elec.id, nombre="Lista 1")
        self.db.add_all([v1, cand])
        self.db.commit()
        self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)

        # Una vez abierta, cambiar regla_votacion debe ser 409
        resp = self.client.put(
            f"/api/elections/{elec.id}",
            json={"regla_votacion": "Un voto por familia"},
            headers=self.headers_admin
        )
        self.assertEqual(resp.status_code, 409)
        self.assertIn("Parámetros estructurales congelados", resp.json()["detail"])

    def test_freezing_candidates_and_padron_when_open(self):
        """Verifica que padrón, comisión y candidaturas queden congelados (409 Conflict) tras apertura"""
        elec = Election(
            nombre="Elección Congelada",
            school_id=self.school.id,
            estado="Borrador"
        )
        self.db.add(elec)
        self.db.flush()

        v1 = Voter(election_id=elec.id, rut="11.111.111-1", rut_normalizado="111111111", nombre="Elector Inicial")
        cand1 = Candidate(election_id=elec.id, nombre="Candidato Inicial")
        self.db.add_all([v1, cand1])
        self.db.commit()

        # Abrir elección
        self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)

        # 1. Intentar agregar candidato -> 409
        resp_cand = self.client.post(
            f"/api/elections/{elec.id}/candidates",
            json={"nombre": "Nuevo Candidato No Autorizado"},
            headers=self.headers_admin
        )
        self.assertEqual(resp_cand.status_code, 409)
        self.assertIn("congelada tras la apertura", resp_cand.json()["detail"])

        # 2. Intentar eliminar candidato -> 409
        resp_del_cand = self.client.delete(
            f"/api/elections/{elec.id}/candidates/{cand1.id}",
            headers=self.headers_admin
        )
        self.assertEqual(resp_del_cand.status_code, 409)
        self.assertIn("congelada tras la apertura", resp_del_cand.json()["detail"])

        # 3. Intentar agregar elector manual -> 409
        resp_voter = self.client.post(
            f"/api/elections/{elec.id}/voters",
            json={"rut": "18.345.678-4", "nombre": "Elector Extemporáneo"},
            headers=self.headers_admin
        )
        self.assertEqual(resp_voter.status_code, 409)
        self.assertIn("congelado tras la apertura", resp_voter.json()["detail"])

        # 4. Intentar agregar miembro de comisión -> 409
        resp_com = self.client.post(
            f"/api/elections/{elec.id}/comite",
            json={"nombre": "Vocal Tardío", "rut": "12.345.678-5", "cargo": "Vocal"},
            headers=self.headers_admin
        )
        self.assertEqual(resp_com.status_code, 409)
        self.assertIn("congelada", resp_com.json()["detail"])

    def test_full_state_lifecycle_to_finalizada(self):
        """Transición completa: Borrador -> Abierta -> Cerrada -> Finalizada"""
        elec = Election(nombre="Elección Ciclo", school_id=self.school.id, estado="Borrador")
        self.db.add(elec)
        self.db.flush()

        v = Voter(election_id=elec.id, rut="11.111.111-1", rut_normalizado="111111111", nombre="Votante")
        c = Candidate(election_id=elec.id, nombre="Lista Unica")
        self.db.add_all([v, c])
        self.db.commit()

        # No se puede finalizar desde Borrador
        resp_fin = self.client.post(f"/api/elections/{elec.id}/finalizar", headers=self.headers_admin)
        self.assertEqual(resp_fin.status_code, 400)

        # Abrir
        r_abrir = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(r_abrir.status_code, 200)

        # No se puede finalizar desde Abierta
        resp_fin2 = self.client.post(f"/api/elections/{elec.id}/finalizar", headers=self.headers_admin)
        self.assertEqual(resp_fin2.status_code, 400)

        # Cerrar
        r_cerrar = self.client.post(f"/api/elections/{elec.id}/cerrar", headers=self.headers_admin)
        self.assertEqual(r_cerrar.status_code, 200)
        self.assertEqual(r_cerrar.json()["estado"], "Cerrada")

        # Finalizar
        r_final = self.client.post(f"/api/elections/{elec.id}/finalizar", headers=self.headers_admin)
        self.assertEqual(r_final.status_code, 200)
        self.assertEqual(r_final.json()["estado"], "Finalizada")

        # Finalizada es terminal: no se puede re-abrir ni re-cerrar
        r_reabrir = self.client.post(f"/api/elections/{elec.id}/abrir", headers=self.headers_admin)
        self.assertEqual(r_reabrir.status_code, 400)

    def test_utc_time_window_restrictions(self):
        """Validación de autoridad horaria en UTC en /api/voting/submit"""
        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Horarios",
            school_id=self.school.id,
            estado="Abierta",
            regla_votacion="Un voto por persona",
            fecha_inicio=now + timedelta(hours=2),  # Inicia en 2 horas
            fecha_fin=now + timedelta(hours=5)
        )
        self.db.add(elec)
        self.db.flush()

        v = Voter(
            election_id=elec.id,
            rut="11.111.111-1",
            rut_normalizado="111111111",
            nombre="Votante Adelantado",
            token_votacion="token-adelantado-123",
            estado="Pendiente"
        )
        c = Candidate(election_id=elec.id, nombre="Candidato")
        ent = VotingEntitlement(election_id=elec.id, unit_key="RUT:111111111", estado="Pendiente")
        self.db.add_all([v, c, ent])
        self.db.commit()

        # Voto antes de fecha_inicio -> 409
        resp = self.client.post("/api/voting/submit", json={"token": "token-adelantado-123", "candidate_id": c.id})
        self.assertEqual(resp.status_code, 409)
        self.assertIn("aún no inicia", resp.json()["detail"])

        # Modificar a expirada en el pasado
        elec.fecha_inicio = now - timedelta(hours=5)
        elec.fecha_fin = now - timedelta(hours=1)
        self.db.commit()

        # Voto después de fecha_fin -> 409
        resp2 = self.client.post("/api/voting/submit", json={"token": "token-adelantado-123", "candidate_id": c.id})
        self.assertEqual(resp2.status_code, 409)
        self.assertIn("ha concluido por expiración de plazo", resp2.json()["detail"])


# -----------------------------------------------------------------------------
# CONCURRENCY SUITE ON REAL POSTGRESQL (Port 5439)
# -----------------------------------------------------------------------------
PG_TEST_URL = os.getenv("S2_CONCURRENCY_DATABASE_URL", "")


class TestPR3PostgresConcurrency(unittest.TestCase):
    """
    A4 - P0 & B1: Pruebas de estrés y concurrencia sobre PostgreSQL 16 real.
    Garantía de un solo voto (1 persona y 1 familia) ante 20+ hilos concurrentes
    y ausencia de deadlocks entre votos y cierre de elección.
    """
    @classmethod
    def setUpClass(cls):
        if not PG_TEST_URL:
            if os.getenv("REQUIRE_S2_SERVICES") == "1":
                raise RuntimeError("S2_CONCURRENCY_DATABASE_URL es obligatoria en integración.")
            raise unittest.SkipTest("S2_CONCURRENCY_DATABASE_URL no configurada")
        try:
            cls.engine = create_engine(
                PG_TEST_URL,
                pool_size=35,
                max_overflow=25,
                connect_args={"options": "-c timezone=utc"}
            )
            with cls.engine.connect() as conn:
                pass
            cls.pg_available = True
        except Exception:
            if os.getenv("REQUIRE_S2_SERVICES") == "1":
                raise
            cls.pg_available = False
            return

        cls.Session = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        if not self.pg_available:
            self.skipTest("Servidor PostgreSQL 16 no disponible en 127.0.0.1:5439")

        self.engine.dispose()
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        _failed_attempts.clear()

        def get_db_pg():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = get_db_pg
        self.client = TestClient(app)

    def tearDown(self):
        if self.pg_available:
            app.dependency_overrides.clear()
            self.engine.dispose()

    def test_concurrent_votes_same_voter_token_exactly_one_succeeds(self):
        """
        25 hilos intentan votar simultáneamente con el MISMO token de elector.
        PostgreSQL debe admitir exactamente 1 voto y rechazar 24 con 409 Conflict.
        """
        db = self.Session()
        school = School(nombre="Colegio San Pedro", rbd="99999-9", comuna="Las Condes")
        db.add(school)
        db.flush()

        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Concurrente Individual",
            school_id=school.id,
            estado="Abierta",
            regla_votacion="Un voto por persona",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(hours=1)
        )
        db.add(elec)
        db.flush()

        voter = Voter(
            election_id=elec.id,
            rut="15.111.222-3",
            rut_normalizado="151112223",
            nombre="Elector Concurrente",
            token_votacion="token-concurrente-indiv",
            estado="Pendiente"
        )
        cand1 = Candidate(election_id=elec.id, nombre="Lista Alpha")
        cand2 = Candidate(election_id=elec.id, nombre="Lista Beta")
        ent = VotingEntitlement(
            election_id=elec.id,
            unit_key=derive_entitlement_key(elec.id, "RUT:151112223"),
            estado="Pendiente"
        )
        db.add_all([voter, cand1, cand2, ent])
        db.commit()

        # Guardar IDs escalares antes de cerrar la sesión
        elec_id = elec.id
        voter_id = voter.id
        cand1_id = cand1.id
        cand2_id = cand2.id
        ent_id = ent.id
        db.close()

        concurrency = 25
        results = []

        def fire_vote(i):
            client = TestClient(app)
            cand_id = cand1_id if i % 2 == 0 else cand2_id
            headers = {"X-Forwarded-For": f"192.168.10.{i+1}"}
            resp = client.post(
                "/api/voting/submit",
                json={
                    "token": "token-concurrente-indiv",
                    "candidate_id": cand_id
                },
                headers=headers
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(fire_vote, i) for i in range(concurrency)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        status_codes = [r[0] for r in results]
        success_count = status_codes.count(200)
        conflict_count = status_codes.count(409) + status_codes.count(400)

        self.assertEqual(success_count, 1, f"Debió registrarse exactamente 1 voto exitoso. Obtenidos: {success_count}. Respuestas: {status_codes}")
        self.assertEqual(conflict_count, concurrency - 1, f"Los restantes {concurrency - 1} deben ser rechazados (409 o 400 tras revocación). Respuestas: {status_codes}")

        # Verificar integridad en la base de datos PostgreSQL
        db_check = self.Session()
        total_votes = db_check.query(Vote).filter(Vote.election_id == elec_id).count()
        voter_check = db_check.query(Voter).filter(Voter.id == voter_id).first()
        ent_check = db_check.query(VotingEntitlement).filter(VotingEntitlement.id == ent_id).first()

        self.assertEqual(total_votes, 1, "La tabla Vote debe contener exactamente 1 registro")
        self.assertEqual(voter_check.estado, "Votó")
        self.assertEqual(ent_check.estado, "Consumido")
        db_check.close()

    def test_concurrent_votes_same_family_multiple_tokens_exactly_one_succeeds(self):
        """
        25 hilos intentan votar simultáneamente con DOS tokens distintos de la MISMA familia.
        PostgreSQL debe admitir exactamente 1 voto familiar y rechazar 24 con 409 Conflict.
        """
        db = self.Session()
        school = School(nombre="Colegio Familia Test", rbd="88888-8", comuna="Santiago")
        db.add(school)
        db.flush()

        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Concurrente Familiar",
            school_id=school.id,
            estado="Abierta",
            regla_votacion="Un voto por familia",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(hours=1)
        )
        db.add(elec)
        db.flush()

        voter_madre = Voter(
            election_id=elec.id,
            rut="14.222.333-4",
            rut_normalizado="142223334",
            nombre="Madre Familia",
            familia_id="FAM-P0-999",
            token_votacion="token-madre-999",
            estado="Pendiente"
        )
        voter_padre = Voter(
            election_id=elec.id,
            rut="13.111.555-6",
            rut_normalizado="131115556",
            nombre="Padre Familia",
            familia_id="FAM-P0-999",
            token_votacion="token-padre-999",
            estado="Pendiente"
        )
        cand = Candidate(election_id=elec.id, nombre="Lista Familiar")
        ent = VotingEntitlement(
            election_id=elec.id,
            unit_key=derive_entitlement_key(elec.id, "FAM:FAM-P0-999"),
            estado="Pendiente"
        )
        db.add_all([voter_madre, voter_padre, cand, ent])
        db.commit()

        # Guardar IDs escalares antes de cerrar
        elec_id = elec.id
        cand_id = cand.id
        ent_id = ent.id
        db.close()

        concurrency = 25
        results = []

        def fire_family_vote(i):
            client = TestClient(app)
            token = "token-madre-999" if i % 2 == 0 else "token-padre-999"
            headers = {"X-Forwarded-For": f"192.168.20.{i+1}"}
            resp = client.post(
                "/api/voting/submit",
                json={
                    "token": token,
                    "candidate_id": cand_id
                },
                headers=headers
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(fire_family_vote, i) for i in range(concurrency)]
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

        status_codes = [r[0] for r in results]
        success_count = status_codes.count(200)
        conflict_count = status_codes.count(409) + status_codes.count(400)

        self.assertEqual(success_count, 1, f"Debió registrarse exactamente 1 voto familiar. Obtenidos: {success_count}. Respuestas: {status_codes}")
        self.assertEqual(conflict_count, concurrency - 1, f"Los restantes {concurrency - 1} deben ser rechazados (409 o 400 tras revocación). Respuestas: {status_codes}")

        # Verificar integridad en PostgreSQL
        db_check = self.Session()
        total_votes = db_check.query(Vote).filter(Vote.election_id == elec_id).count()
        voters = db_check.query(Voter).filter(Voter.familia_id == "FAM-P0-999").all()
        ent_check = db_check.query(VotingEntitlement).filter(VotingEntitlement.id == ent_id).first()

        self.assertEqual(total_votes, 1, "La tabla Vote debe registrar un único voto para toda la familia")
        self.assertEqual(ent_check.estado, "Consumido")

        voted_count = sum(1 for v in voters if v.estado == "Votó")
        blocked_count = sum(1 for v in voters if v.estado == "Bloqueado")
        self.assertEqual(voted_count, 1, "Exactamente 1 miembro de la familia debe quedar con estado 'Votó'")
        self.assertEqual(blocked_count, 1, "El otro miembro de la familia debe quedar con estado 'Bloqueado'")
        db_check.close()

    def test_concurrent_voting_and_closing_race_no_deadlocks(self):
        """
        Carrera concurrente: 20 hilos votando con tokens válidos mientras otro hilo llama a /cerrar.
        El orden consistente de locks (Election -> VotingEntitlement -> Voter) garantiza ausencia de deadlocks.
        """
        db = self.Session()
        school = School(nombre="Colegio Carrera Lock", rbd="77777-7", comuna="Santiago")
        db.add(school)
        db.flush()

        admin = User(
            email="admin_pg@test.cl",
            nombre="Admin PG",
            password_hash=get_password_hash("Pass123!"),
            rol="Administrador General"
        )
        db.add(admin)
        db.flush()

        token_admin = create_access_token(data={"sub": admin.email, "rol": admin.rol})
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        now = datetime.now(timezone.utc)
        elec = Election(
            nombre="Elección Carrera",
            school_id=school.id,
            estado="Abierta",
            regla_votacion="Un voto por persona",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(hours=1)
        )
        db.add(elec)
        db.flush()

        cand = Candidate(election_id=elec.id, nombre="Candidato Único")
        db.add(cand)
        db.flush()

        # Crear 20 electores distintos
        for i in range(20):
            rut_clean = f"100000{i:02d}0"
            v = Voter(
                election_id=elec.id,
                rut=f"10.000.{i:02d}-0",
                rut_normalizado=rut_clean,
                nombre=f"Votante {i}",
                token_votacion=f"tok-carrera-{i}",
                estado="Pendiente"
            )
            ent = VotingEntitlement(
                election_id=elec.id,
                unit_key=derive_entitlement_key(elec.id, f"RUT:{rut_clean}"),
                estado="Pendiente"
            )
            db.add_all([v, ent])

        db.commit()

        elec_id = elec.id
        cand_id = cand.id
        db.close()

        vote_results = []
        close_result = []

        def submit_one(i):
            client = TestClient(app)
            headers = {"X-Forwarded-For": f"192.168.30.{i+1}"}
            resp = client.post(
                "/api/voting/submit",
                json={
                    "token": f"tok-carrera-{i}",
                    "candidate_id": cand_id
                },
                headers=headers
            )
            return resp.status_code

        def close_one():
            client = TestClient(app)
            resp = client.post(f"/api/elections/{elec_id}/cerrar", headers=headers_admin)
            return resp.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            # Lanzar votos y cierre simultáneamente
            vote_futures = [executor.submit(submit_one, i) for i in range(20)]
            close_future = executor.submit(close_one)

            for f in concurrent.futures.as_completed(vote_futures):
                vote_results.append(f.result())
            close_result.append(close_future.result())

        # El cierre debe haber retornado 200 (o 400 si ya estaba cerrada, pero aquí partió abierta)
        self.assertEqual(close_result[0], 200, "El cierre de la elección debió ser exitoso")

        # Ningún hilo debió morir por deadlock (500)
        self.assertNotIn(500, vote_results, "Ninguna petición debió fallar por deadlock de base de datos")

        # Todos los códigos deben ser 200 (voto aceptado antes del lock de cierre) o 409 (rechazado tras el lock de cierre)
        for code in vote_results:
            self.assertIn(code, [200, 409])

        # Verificar consistencia en PostgreSQL
        db_check = self.Session()
        final_elec = db_check.query(Election).filter(Election.id == elec_id).first()
        self.assertEqual(final_elec.estado, "Cerrada")

        total_votos = db_check.query(Vote).filter(Vote.election_id == elec_id).count()
        success_votos = vote_results.count(200)
        self.assertEqual(total_votos, success_votos, "El conteo en la base de datos debe coincidir exactamente con los 200 OK")
        db_check.close()


if __name__ == "__main__":
    unittest.main()
