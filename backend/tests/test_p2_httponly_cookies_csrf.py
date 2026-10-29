import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.config import settings
from app.database import Base, get_db
from app.models import User, School, Election, AuditLog
from app.auth import get_password_hash, create_access_token, ROLE_SUPERADMIN

# In-memory SQLite for isolated test execution
SQLITE_DATABASE_URL = "sqlite:///:memory:"
sqlite_engine = create_engine(
    SQLITE_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLiteSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)


def override_get_db():
    db = SQLiteSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestP2HttpOnlyCookiesAndCSRF(unittest.TestCase):
    """
    Batería de pruebas automatizadas para P2:
    - Emisión de cookies HttpOnly (access_token) y CSRF (csrf_token) en /api/auth/login
    - Autenticación transparente mediante cookie HttpOnly sin cabecera Authorization
    - Protección CSRF activa (Double Submit Cookie) para mutaciones (POST, PUT, DELETE)
    - Expiración de cookies en /api/auth/logout y registro en bitácora de auditoría
    - Retrocompatibilidad con cabecera Authorization: Bearer
    """

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def setUp(self):
        Base.metadata.create_all(bind=sqlite_engine)
        self.db = SQLiteSessionLocal()
        self.client = TestClient(app)

        # Crear usuario administrador para pruebas
        self.user = User(
            nombre="Super Admin P2",
            email="admin_p2@theogen.cl",
            password_hash=get_password_hash("AdminP2Password123"),
            rol=ROLE_SUPERADMIN,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)

    def test_01_login_issues_httponly_and_csrf_cookies(self):
        """Verifica que /auth/login emita access_token como HttpOnly y csrf_token legible"""
        res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(res.status_code, 200)

        # 1. Verificar cookies emitidas
        cookies = res.cookies
        self.assertIn("access_token", cookies)
        self.assertIn("csrf_token", cookies)

        # 2. Verificar cabeceras Set-Cookie
        set_cookie_headers = res.headers.get_list("set-cookie") if hasattr(res.headers, "get_list") else [res.headers.get("set-cookie", "")]
        full_set_cookie = "; ".join(set_cookie_headers)

        # access_token debe ser HttpOnly
        self.assertIn("access_token=", full_set_cookie)
        self.assertIn("httponly", full_set_cookie.lower())
        self.assertIn("samesite=lax", full_set_cookie.lower())

        # 3. Verificar cuerpo de respuesta
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("csrf_token", data)
        self.assertEqual(data["user"]["email"], "admin_p2@theogen.cl")

    def test_02_authenticate_with_cookie_only(self):
        """Verifica que /auth/me autentique exitosamente solo con la cookie HttpOnly"""
        # Iniciar sesión para obtener cookie
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)

        # TestClient retiene las cookies automáticamente; hacer petición sin cabecera Authorization
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 200)
        self.assertEqual(me_res.json()["email"], "admin_p2@theogen.cl")

    def test_03_csrf_blocks_mutation_when_header_missing(self):
        """Verifica que peticiones mutantes (POST) con cookie de sesión sean bloqueadas si falta X-CSRF-Token"""
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)

        # Intentar crear un colegio sin enviar la cabecera X-CSRF-Token
        create_res = self.client.post(
            "/api/schools",
            json={"nombre": "Colegio Sin CSRF", "rbd": "9999-1"}
        )
        self.assertEqual(create_res.status_code, 403)
        self.assertIn("Token CSRF", create_res.json()["detail"])

    def test_04_csrf_blocks_mutation_when_header_mismatched(self):
        """Verifica que peticiones mutantes con token CSRF erróneo sean bloqueadas con 403"""
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)

        # Enviar token CSRF falso
        create_res = self.client.post(
            "/api/schools",
            json={"nombre": "Colegio CSRF Mismatch", "rbd": "9999-2"},
            headers={"X-CSRF-Token": "token_invalido_de_otro_sitio"}
        )
        self.assertEqual(create_res.status_code, 403)
        self.assertIn("Token CSRF", create_res.json()["detail"])

    def test_05_csrf_allows_mutation_when_header_matches(self):
        """Verifica que peticiones mutantes con token CSRF válido sean procesadas exitosamente"""
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)
        csrf_token = login_res.cookies.get("csrf_token")
        self.assertIsNotNone(csrf_token)

        # Enviar petición POST con cabecera X-CSRF-Token coincidente
        create_res = self.client.post(
            "/api/schools",
            json={"nombre": "Colegio Con CSRF Válido", "rbd": "12345-6"},
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(create_res.json()["nombre"], "Colegio Con CSRF Válido")

    def test_06_logout_clears_cookies_and_records_audit(self):
        """Verifica que /auth/logout invalide las cookies y registre en bitácora de auditoría"""
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)
        csrf_token = login_res.cookies.get("csrf_token")

        # Ejecutar logout
        logout_res = self.client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token}
        )
        self.assertEqual(logout_res.status_code, 200)
        self.assertIn("cerrada", logout_res.json()["message"])

        # Verificar auditoría
        audit = self.db.query(AuditLog).filter(
            AuditLog.accion == "Cierre de sesión",
            AuditLog.usuario == "admin_p2@theogen.cl"
        ).first()
        self.assertIsNotNone(audit)

        # Intentar acceder a ruta protegida post-logout sin cookies debe dar 401
        self.client.cookies.clear()
        me_res = self.client.get("/api/auth/me")
        self.assertEqual(me_res.status_code, 401)

    def test_07_bearer_token_authorization_header_backward_compatibility(self):
        """Verifica que clientes con cabecera Authorization: Bearer sigan funcionando sin cookies ni CSRF"""
        token = create_access_token(data={
            "sub": "admin_p2@theogen.cl",
            "rol": ROLE_SUPERADMIN,
            "school_id": None,
            "election_id": None
        })

        client_no_cookies = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        # GET con Bearer
        me_res = client_no_cookies.get("/api/auth/me", headers=headers)
        self.assertEqual(me_res.status_code, 200)

        # POST con Bearer (no requiere cabecera CSRF porque Bearer no es vulnerable a CSRF)
        create_res = client_no_cookies.post(
            "/api/schools",
            json={"nombre": "Colegio Vía Bearer Header", "rbd": "77777-7"},
            headers=headers
        )
        self.assertEqual(create_res.status_code, 201)
        self.assertEqual(create_res.json()["nombre"], "Colegio Vía Bearer Header")

    def test_08_public_voting_endpoints_exempt_from_csrf(self):
        """Verifica que los endpoints públicos de la sala de votación no requieran token CSRF"""
        # Crear elección de prueba
        school = School(nombre="Colegio Sala Votación", rbd="5555-5")
        self.db.add(school)
        self.db.commit()

        # Validar token de votación no existente da 404/400 pero NO 403 CSRF
        res = self.client.post(
            "/api/voting/validate-token",
            json={"token": "3a8f803d-0ccb-48b7-89f7-d92aa4c729de"}
        )
        self.assertNotEqual(res.status_code, 403)

    def test_09_authorization_header_does_not_bypass_csrf_for_cookie_session(self):
        login_res = self.client.post(
            "/api/auth/login",
            json={"email": "admin_p2@theogen.cl", "password": "AdminP2Password123"}
        )
        self.assertEqual(login_res.status_code, 200)
        access_token = login_res.cookies.get("access_token")

        create_res = self.client.post(
            "/api/schools",
            json={"nombre": "Colegio CSRF Bypass", "rbd": "88888-8"},
            headers={"Authorization": f"Bearer {access_token}"}
        )

        self.assertEqual(create_res.status_code, 403)
        self.assertIn("Token CSRF", create_res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
