import sys
import os
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.database import Base, get_db
from app.models import User, School, Election, Candidate, Voter
from app.auth import get_password_hash, create_access_token

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestPR2MultiTenantRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        # 1. Crear Colegio A y Colegio B
        self.school_a = School(nombre="Colegio A", rbd="11111-1", comuna="Santiago")
        self.school_b = School(nombre="Colegio B", rbd="22222-2", comuna="Providencia")
        self.db.add_all([self.school_a, self.school_b])
        self.db.flush()

        # 2. Crear Elecciones para Colegio A y Colegio B
        now = datetime.now(timezone.utc)
        self.election_a1 = Election(
            nombre="Elección A1",
            school_id=self.school_a.id,
            estado="Borrador",
            fecha_inicio=now,
            fecha_fin=now + timedelta(days=1),
            tipo_votacion="Centro de Padres"
        )
        self.election_a2 = Election(
            nombre="Elección A2",
            school_id=self.school_a.id,
            estado="Borrador",
            fecha_inicio=now,
            fecha_fin=now + timedelta(days=1),
            tipo_votacion="Centro de Alumnos"
        )
        self.election_b1 = Election(
            nombre="Elección B1",
            school_id=self.school_b.id,
            estado="Borrador",
            fecha_inicio=now,
            fecha_fin=now + timedelta(days=1),
            tipo_votacion="Centro de Padres"
        )
        self.db.add_all([self.election_a1, self.election_a2, self.election_b1])
        self.db.flush()

        # 3. Crear Usuarios con diferentes roles y ámbitos
        # Superadmin Global
        self.user_superadmin = User(
            nombre="Superadmin Global",
            email="superadmin@theogen.cl",
            password_hash=get_password_hash("PassSuper123"),
            rol="Administrador General",
            school_id=None,
            election_id=None
        )

        # Responsable Institucional Colegio A
        self.user_manager_a = User(
            nombre="Director Colegio A",
            email="director@colegioa.cl",
            password_hash=get_password_hash("PassColA123"),
            rol="Responsable Institucional",
            school_id=self.school_a.id,
            election_id=None
        )

        # Responsable Institucional Colegio B
        self.user_manager_b = User(
            nombre="Directora Colegio B",
            email="directora@colegiob.cl",
            password_hash=get_password_hash("PassColB123"),
            rol="Responsable Institucional",
            school_id=self.school_b.id,
            election_id=None
        )

        # Comisión Electoral Elección A1
        self.user_comision_a1 = User(
            nombre="Presidente Comisión A1",
            email="comision@elecciona1.cl",
            password_hash=get_password_hash("PassComA123"),
            rol="Comisión Electoral",
            school_id=self.school_a.id,
            election_id=self.election_a1.id
        )

        self.db.add_all([
            self.user_superadmin,
            self.user_manager_a,
            self.user_manager_b,
            self.user_comision_a1
        ])
        self.db.commit()

        # Tokens JWT
        self.token_superadmin = create_access_token({"sub": self.user_superadmin.email, "rol": self.user_superadmin.rol})
        self.token_manager_a = create_access_token({"sub": self.user_manager_a.email, "rol": self.user_manager_a.rol})
        self.token_manager_b = create_access_token({"sub": self.user_manager_b.email, "rol": self.user_manager_b.rol})
        self.token_comision_a1 = create_access_token({"sub": self.user_comision_a1.email, "rol": self.user_comision_a1.rol})

        self.headers_super = {"Authorization": f"Bearer {self.token_superadmin}"}
        self.headers_manager_a = {"Authorization": f"Bearer {self.token_manager_a}"}
        self.headers_manager_b = {"Authorization": f"Bearer {self.token_manager_b}"}
        self.headers_comision_a1 = {"Authorization": f"Bearer {self.token_comision_a1}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=test_engine)

    def test_01_cross_school_access_forbidden(self):
        """IDOR-01: Manager of School A cannot read or modify School B details"""
        # Read attempt
        resp_read = self.client.get(f"/api/schools/{self.school_b.id}", headers=self.headers_manager_a)
        self.assertEqual(resp_read.status_code, 403, f"Expected 403 on cross-school read, got {resp_read.status_code}")

        # Write attempt
        resp_write = self.client.put(
            f"/api/schools/{self.school_b.id}",
            json={"nombre": "Colegio B Alterado"},
            headers=self.headers_manager_a
        )
        self.assertEqual(resp_write.status_code, 403, f"Expected 403 on cross-school write, got {resp_write.status_code}")

    def test_02_cross_election_access_forbidden(self):
        """IDOR-02: Manager of School A cannot access or modify elections belonging to School B"""
        resp_election = self.client.get(f"/api/elections/{self.election_b1.id}", headers=self.headers_manager_a)
        self.assertEqual(resp_election.status_code, 403, f"Expected 403 on foreign election access, got {resp_election.status_code}")

        resp_update = self.client.put(
            f"/api/elections/{self.election_b1.id}",
            json={"nombre": "Hackeada"},
            headers=self.headers_manager_a
        )
        self.assertEqual(resp_update.status_code, 403, f"Expected 403 on foreign election update, got {resp_update.status_code}")

    def test_03_cross_school_voters_forbidden(self):
        """IDOR-03: Manager of School A cannot list or add voters to School B elections"""
        resp_voters = self.client.get(f"/api/elections/{self.election_b1.id}/voters", headers=self.headers_manager_a)
        self.assertEqual(resp_voters.status_code, 403, f"Expected 403 on foreign election voters list, got {resp_voters.status_code}")

        resp_create_voter = self.client.post(
            f"/api/elections/{self.election_b1.id}/voters",
            json={"rut": "11.111.111-1", "nombre": "Elector Infiltrado"},
            headers=self.headers_manager_a
        )
        self.assertEqual(resp_create_voter.status_code, 403, f"Expected 403 on foreign voter creation, got {resp_create_voter.status_code}")

    def test_04_cross_school_candidates_forbidden(self):
        """IDOR-04: Manager of School A cannot list, create or delete candidates in School B"""
        resp_cand = self.client.get(f"/api/elections/{self.election_b1.id}/candidates", headers=self.headers_manager_a)
        self.assertEqual(resp_cand.status_code, 403, f"Expected 403 on foreign candidate list, got {resp_cand.status_code}")

    def test_05_electoral_committee_scope_isolation(self):
        """IDOR-05: Commission assigned to Election A1 cannot access Election A2 in the same school"""
        resp = self.client.get(f"/api/elections/{self.election_a2.id}", headers=self.headers_comision_a1)
        self.assertEqual(resp.status_code, 403, f"Expected 403 on commission out-of-scope election, got {resp.status_code}")

        # But can access its own assigned election A1
        resp_own = self.client.get(f"/api/elections/{self.election_a1.id}", headers=self.headers_comision_a1)
        self.assertEqual(resp_own.status_code, 200, f"Expected 200 on own election, got {resp_own.status_code}")

    def test_06_superadmin_retains_full_access(self):
        """RBAC-01: Administrador General has global access across all schools and elections"""
        resp_a = self.client.get(f"/api/schools/{self.school_a.id}", headers=self.headers_super)
        self.assertEqual(resp_a.status_code, 200)

        resp_b = self.client.get(f"/api/schools/{self.school_b.id}", headers=self.headers_super)
        self.assertEqual(resp_b.status_code, 200)

        resp_el = self.client.get(f"/api/elections/{self.election_b1.id}", headers=self.headers_super)
        self.assertEqual(resp_el.status_code, 200)

    def test_07_scoped_listings(self):
        """RBAC-02: Listing endpoints are scoped server-side to the user's institution/election"""
        # Manager A listing schools: only receives School A
        resp_schools = self.client.get("/api/schools", headers=self.headers_manager_a)
        self.assertEqual(resp_schools.status_code, 200)
        schools_data = resp_schools.json()
        school_ids = [s["id"] for s in schools_data]
        self.assertIn(self.school_a.id, school_ids)
        self.assertNotIn(self.school_b.id, school_ids)

        # Manager A listing elections: only receives Election A1 and A2, NOT B1
        resp_elections = self.client.get("/api/elections", headers=self.headers_manager_a)
        self.assertEqual(resp_elections.status_code, 200)
        elections_data = resp_elections.json()
        el_ids = [e["id"] for e in elections_data]
        self.assertIn(self.election_a1.id, el_ids)
        self.assertIn(self.election_a2.id, el_ids)
        self.assertNotIn(self.election_b1.id, el_ids)

    def test_08_cross_school_reports_and_scrutiny_forbidden(self):
        """IDOR-08: Manager of School A cannot access scrutiny or PDF acts of School B"""
        # Scrutiny
        resp_scrutiny = self.client.get(f"/api/reports/election/{self.election_b1.id}/scrutiny", headers=self.headers_manager_a)
        self.assertEqual(resp_scrutiny.status_code, 403, f"Expected 403, got {resp_scrutiny.status_code}")

        # PDF Apertura
        resp_pdf_ap = self.client.get(f"/api/reports/election/{self.election_b1.id}/acta-apertura/pdf", headers=self.headers_manager_a)
        self.assertEqual(resp_pdf_ap.status_code, 403, f"Expected 403, got {resp_pdf_ap.status_code}")

        # PDF Cierre
        resp_pdf_ci = self.client.get(f"/api/reports/election/{self.election_b1.id}/acta-cierre/pdf", headers=self.headers_manager_a)
        self.assertEqual(resp_pdf_ci.status_code, 403, f"Expected 403, got {resp_pdf_ci.status_code}")

    def test_09_comision_cannot_create_election_or_modify_school(self):
        """RBAC-03: Comisión Electoral cannot create elections or modify schools"""
        # Attempt to create election
        resp_create = self.client.post(
            "/api/elections",
            json={
                "nombre": "Elección Ilegítima",
                "school_id": self.school_a.id,
                "tipo_votacion": "Centro de Padres"
            },
            headers=self.headers_comision_a1
        )
        self.assertEqual(resp_create.status_code, 403, f"Expected 403, got {resp_create.status_code}")

        # Attempt to update school
        resp_update_school = self.client.put(
            f"/api/schools/{self.school_a.id}",
            json={"nombre": "Colegio A Alterado por Comisión"},
            headers=self.headers_comision_a1
        )
        self.assertEqual(resp_update_school.status_code, 403, f"Expected 403, got {resp_update_school.status_code}")

    def test_10_manager_cannot_create_election_in_foreign_school(self):
        """IDOR-09: Manager of School A cannot create elections targeting School B"""
        resp = self.client.post(
            "/api/elections",
            json={
                "nombre": "Invasión Electoral",
                "school_id": self.school_b.id,
                "tipo_votacion": "Centro de Padres"
            },
            headers=self.headers_manager_a
        )
        self.assertEqual(resp.status_code, 403, f"Expected 403, got {resp.status_code}")

    def test_11_manager_cannot_create_new_school(self):
        """RBAC-04: Only Superadmin can create new institutions"""
        resp_manager = self.client.post(
            "/api/schools",
            json={"nombre": "Nuevo Colegio Trucho", "rbd": "99999-9"},
            headers=self.headers_manager_a
        )
        self.assertEqual(resp_manager.status_code, 403, f"Expected 403 for Manager, got {resp_manager.status_code}")

        resp_super = self.client.post(
            "/api/schools",
            json={"nombre": "Nuevo Colegio Oficial", "rbd": "88888-8"},
            headers=self.headers_super
        )
        self.assertEqual(resp_super.status_code, 201, f"Expected 201 for Superadmin, got {resp_super.status_code}")

    def test_12_dashboard_stats_scoped_per_role(self):
        """RBAC-05: Dashboard statistics are scoped to the user's institution"""
        # Superadmin sees all 3 elections
        resp_super = self.client.get("/api/reports/dashboard-stats", headers=self.headers_super)
        self.assertEqual(resp_super.status_code, 200)
        self.assertEqual(resp_super.json()["total_elecciones"], 3)

        # Manager A sees only 2 elections (A1 and A2)
        resp_mgr = self.client.get("/api/reports/dashboard-stats", headers=self.headers_manager_a)
        self.assertEqual(resp_mgr.status_code, 200)
        self.assertEqual(resp_mgr.json()["total_elecciones"], 2)

        # Comisión A1 sees only 1 election (A1)
        resp_com = self.client.get("/api/reports/dashboard-stats", headers=self.headers_comision_a1)
        self.assertEqual(resp_com.status_code, 200)
        self.assertEqual(resp_com.json()["total_elecciones"], 1)

    def test_13_audit_logs_scoped(self):
        """RBAC-06: Audit logs are scoped to user institution unless superadmin"""
        # Create an audit log for school A and school B
        from app.auth import log_audit
        log_audit(self.db, accion="Prueba School A", detalle="Detalle A", usuario="director@colegioa.cl", school_id=self.school_a.id)
        log_audit(self.db, accion="Prueba School B", detalle="Detalle B", usuario="directora@colegiob.cl", school_id=self.school_b.id)

        # Manager A queries logs
        resp_mgr = self.client.get("/api/audit/logs", headers=self.headers_manager_a)
        self.assertEqual(resp_mgr.status_code, 200)
        logs = resp_mgr.json()
        actions = [l["accion"] for l in logs]
        self.assertIn("Prueba School A", actions)
        self.assertNotIn("Prueba School B", actions)

        # Superadmin queries logs
        resp_super = self.client.get("/api/audit/logs", headers=self.headers_super)
        self.assertEqual(resp_super.status_code, 200)
        super_actions = [l["accion"] for l in resp_super.json()]
        self.assertIn("Prueba School A", super_actions)
        self.assertIn("Prueba School B", super_actions)

    def test_14_voter_credentials_and_tokens_idor_forbidden(self):
        """IDOR-10: Manager A cannot generate credentials or view dispatch for School B"""
        resp_tok = self.client.post(f"/api/elections/{self.election_b1.id}/voters/generate-tokens", headers=self.headers_manager_a)
        self.assertEqual(resp_tok.status_code, 403)

        resp_disp = self.client.get(f"/api/elections/{self.election_b1.id}/voters/simulate-email-dispatch", headers=self.headers_manager_a)
        self.assertEqual(resp_disp.status_code, 403)

    def test_15_candidate_delete_idor_forbidden(self):
        """IDOR-11: Manager A cannot delete candidates belonging to School B"""
        resp = self.client.delete(f"/api/elections/{self.election_b1.id}/candidates/999", headers=self.headers_manager_a)
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()

