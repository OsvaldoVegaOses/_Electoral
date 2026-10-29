import sys
import os
import unittest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.database import Base, get_db
from app.models import User, School, Election, Candidate, Voter, Vote, VotingEntitlement
from app.entitlements import derive_entitlement_key
from app.auth import get_password_hash, create_access_token, clear_failed_attempts
from app.schemas import UserLogin

# In-memory SQLite for functional testing
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


class TestPR1SecurityContainment(unittest.TestCase):
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
        clear_failed_attempts("testclient")
        clear_failed_attempts("127.0.0.1")

        # Create Admin User
        self.admin_user = User(
            nombre="Admin Test",
            email="admin@test.cl",
            password_hash=get_password_hash("AdminPass123"),
            rol="Administrador"
        )
        self.db.add(self.admin_user)

        # Create School
        self.school = School(
            nombre="Colegio de Prueba",
            rbd="12345-6",
            comuna="Santiago"
        )
        self.db.add(self.school)
        self.db.flush()

        # Create Open Election
        now = datetime.now(timezone.utc)
        self.election_open = Election(
            nombre="Elección Abierta Test",
            descripcion="Elección de prueba",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(hours=5),
            estado="Abierta",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por familia"
        )
        self.db.add(self.election_open)

        # Create Closed Election
        self.election_closed = Election(
            nombre="Elección Cerrada Test",
            descripcion="Elección cerrada de prueba",
            fecha_inicio=now - timedelta(days=2),
            fecha_fin=now - timedelta(days=1),
            estado="Cerrada",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por familia"
        )
        self.db.add(self.election_closed)
        self.db.flush()

        # Candidates for open election
        self.cand_a = Candidate(
            nombre="Lista A",
            cargo="Presidencia",
            orden=1,
            election_id=self.election_open.id
        )
        self.cand_b = Candidate(
            nombre="Lista B",
            cargo="Presidencia",
            orden=2,
            election_id=self.election_open.id
        )
        self.db.add_all([self.cand_a, self.cand_b])

        # Voters for open election (family FAM-01)
        self.voter_1 = Voter(
            rut="11.111.111-1",
            nombre="Padre Familia 1",
            correo="padre@fam1.cl",
            familia_id="FAM-01",
            token_votacion="secret-token-voter-1-fam1",
            estado="Pendiente",
            election_id=self.election_open.id
        )
        self.voter_2 = Voter(
            rut="22.222.222-2",
            nombre="Madre Familia 1",
            correo="madre@fam1.cl",
            familia_id="FAM-01",
            token_votacion="secret-token-voter-2-fam1",
            estado="Pendiente",
            election_id=self.election_open.id
        )
        self.db.add_all([self.voter_1, self.voter_2])
        self.db.add(VotingEntitlement(election_id=self.election_open.id,
                                     unit_key=derive_entitlement_key(self.election_open.id, "FAM:FAM-01")))
        self.db.commit()

        # Admin JWT Token
        self.admin_jwt = create_access_token(data={"sub": self.admin_user.email, "rol": self.admin_user.rol})
        self.auth_headers = {"Authorization": f"Bearer {self.admin_jwt}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=test_engine)

    def test_01_voters_list_does_not_expose_voting_tokens(self):
        """VULN-01: GET /elections/{id}/voters must not expose token_votacion in response"""
        response = self.client.get(
            f"/api/elections/{self.election_open.id}/voters",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data), 0)
        for voter in data:
            # token_votacion must either be absent or None/empty
            token_val = voter.get("token_votacion")
            self.assertTrue(
                token_val is None or token_val == "",
                f"Voter {voter.get('nombre')} exposed voting token: {token_val}"
            )

    def test_02_simulate_email_dispatch_does_not_leak_raw_tokens_in_html(self):
        """VULN-02: simulate-email-dispatch must not leak real token in preview_html or links"""
        response = self.client.get(
            f"/api/elections/{self.election_open.id}/voters/simulate-email-dispatch",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for email in data.get("correos_simulados", []):
            preview_html = email.get("preview_html", "")
            # Must not contain raw secret tokens
            self.assertNotIn("secret-token-voter-1-fam1", preview_html)
            self.assertNotIn("secret-token-voter-2-fam1", preview_html)
            # Must not contain URL with ?token=...
            self.assertNotIn("?token=", preview_html)

    def test_03_voting_token_in_query_rejected_must_be_in_body(self):
        """VULN-03: /voting/validate-token must accept token via JSON body, not query param"""
        # Testing via query param should be rejected (422 Unprocessable Entity or 400)
        query_resp = self.client.post(
            f"/api/voting/validate-token?token={self.voter_1.token_votacion}"
        )
        # It must NOT succeed via query parameter
        self.assertNotEqual(query_resp.status_code, 200, "Query param token should not return 200")

        # Testing via JSON Body
        body_resp = self.client.post(
            "/api/voting/validate-token",
            json={"token": self.voter_1.token_votacion}
        )
        self.assertEqual(body_resp.status_code, 200)
        self.assertTrue(body_resp.json()["valido"])

    def test_04_auth_jwt_in_query_string_rejected(self):
        """VULN-04: Protected endpoints must reject ?token=JWT query string"""
        # Attempting to access protected endpoint using ?token= query parameter without Authorization header
        response = self.client.get(
            f"/api/reports/election/{self.election_open.id}/acta-apertura/pdf?token={self.admin_jwt}"
        )
        self.assertEqual(
            response.status_code, 401,
            f"Expected 401 Unauthorized for query JWT, got {response.status_code}"
        )

    def test_05_user_login_schema_accepts_any_password_string(self):
        """VULN-05: UserLogin schema must not enforce complexity on login to avoid locking legacy passwords"""
        try:
            login = UserLogin(email="user@test.cl", password="simplepassword")
            self.assertEqual(login.password, "simplepassword")
        except ValidationError:
            self.fail("UserLogin unexpectedly raised ValidationError for password without digits")

    def test_06_scrutiny_and_acta_cierre_blocked_when_election_is_open(self):
        """VULN-06: Scrutiny and Acta de Cierre must be blocked (403/409) when election is Abierta"""
        scrutiny_resp = self.client.get(
            f"/api/reports/election/{self.election_open.id}/scrutiny",
            headers=self.auth_headers
        )
        self.assertIn(
            scrutiny_resp.status_code, [403, 409],
            f"Expected 403 or 409 for open election scrutiny, got {scrutiny_resp.status_code}"
        )

        acta_resp = self.client.get(
            f"/api/reports/election/{self.election_open.id}/acta-cierre/pdf",
            headers=self.auth_headers
        )
        self.assertIn(
            acta_resp.status_code, [403, 409],
            f"Expected 403 or 409 for open election acta de cierre, got {acta_resp.status_code}"
        )

    def test_07_family_validation_does_not_reveal_voter_name(self):
        """VULN-07: When a family member already voted, validating another token must not leak who voted"""
        # Mark voter_1 as voted
        self.voter_1.estado = "Votó"
        self.voter_1.fecha_voto = datetime.now(timezone.utc)
        self.db.commit()

        # Validate voter_2 (same family)
        resp = self.client.post(
            "/api/voting/validate-token",
            json={"token": self.voter_2.token_votacion}
        )
        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("mensaje", "")
            # Must NOT reveal the name of voter_1 ("Padre Familia 1")
            self.assertNotIn("Padre Familia 1", msg)
            self.assertIn("familia", msg.lower())

    def test_08_rate_limiting_on_voting_validate_token(self):
        """VULN-08: Validation attempts with invalid tokens must trigger rate limiting"""
        test_ip = "192.168.10.50"
        headers = {"X-Forwarded-For": test_ip}
        clear_failed_attempts(test_ip)

        # Trigger failed attempts
        hit_429 = False
        for i in range(12):
            r = self.client.post(
                "/api/voting/validate-token",
                json={"token": f"invalid-token-{i}"},
                headers=headers
            )
            if r.status_code == 429:
                hit_429 = True
                break
        self.assertTrue(hit_429, "Expected 429 Too Many Requests after excessive invalid tokens")


if __name__ == "__main__":
    unittest.main()
