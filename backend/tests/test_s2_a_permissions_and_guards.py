"""
Sprint 2 — PR S2-A: Pruebas de regresión para permisos estrictos, contención y guards.

Verifica:
1. S2-04: Comisión Electoral sin election_id deniega acceso por defecto (403) a elecciones del colegio.
2. S2-04: Comisión Electoral sin election_id en list_elections retorna lista vacía (cero lecturas fuera de ámbito).
3. Comisión Electoral asignada a Elección 1 deniega acceso (403) a Elección 2 del mismo colegio.
4. Comisión Electoral asignada a Elección 1 puede acceder a Elección 1 (200) y solo ve Elección 1 en list_elections.
5. Responsable Institucional de Colegio A deniega acceso (403) a Elecciones de Colegio B (aislamiento horizontal).
6. Validación de ámbito de usuario: rechazo de combinaciones inválidas/contradictorias (UserCreate y helper).
7. Contención PII: en producción sin opt-in explícito, mutaciones de anonimización y purga son bloqueadas (403),
   conservando dry-run (?dry_run=true) y consultas de estado/lectura (200).
"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from app.config import settings
from app.database import Base, get_db
from app.models import School, Election, User, Candidate, Voter
from app.auth import (
    get_password_hash, create_access_token,
    ROLE_SUPERADMIN, ROLE_RESPONSABLE, ROLE_COMISION
)
from app.schemas import UserCreate

# SQLite en memoria aislado
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


class TestS2APermissionsAndGuards(unittest.TestCase):
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

        # Colegio A y Colegio B
        self.school_a = School(nombre="Colegio A", rbd="1001-1")
        self.school_b = School(nombre="Colegio B", rbd="2002-2")
        self.db.add_all([self.school_a, self.school_b])
        self.db.commit()

        # Dos elecciones en Colegio A
        self.election_a1 = Election(
            nombre="Elección A1 - Directiva",
            school_id=self.school_a.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            estado="Borrador",
        )
        self.election_a2 = Election(
            nombre="Elección A2 - Centro Alumnos",
            school_id=self.school_a.id,
            tipo_votacion="Centro de Alumnos",
            regla_votacion="Un voto por persona",
            estado="Borrador",
        )
        # Una elección en Colegio B
        self.election_b1 = Election(
            nombre="Elección B1 - Directiva B",
            school_id=self.school_b.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            estado="Borrador",
        )
        self.db.add_all([self.election_a1, self.election_a2, self.election_b1])
        self.db.commit()

        # Usuarios
        # 1. Superadmin
        self.user_superadmin = User(
            nombre="Super Admin",
            email="superadmin@theogen.cl",
            password_hash=get_password_hash("Pass123456"),
            rol=ROLE_SUPERADMIN,
            school_id=None,
            election_id=None,
        )
        # 2. Responsable Colegio A
        self.user_resp_a = User(
            nombre="Responsable Col A",
            email="responsable_a@theogen.cl",
            password_hash=get_password_hash("Pass123456"),
            rol=ROLE_RESPONSABLE,
            school_id=self.school_a.id,
            election_id=None,
        )
        # 3. Comisión Colegio A con Elección A1
        self.user_comision_a1 = User(
            nombre="Comisión A1",
            email="comision_a1@theogen.cl",
            password_hash=get_password_hash("Pass123456"),
            rol=ROLE_COMISION,
            school_id=self.school_a.id,
            election_id=self.election_a1.id,
        )
        # 4. Comisión Colegio A SIN election_id (caso de vulnerabilidad S2-04)
        self.user_comision_null = User(
            nombre="Comisión Sin Asignar",
            email="comision_null@theogen.cl",
            password_hash=get_password_hash("Pass123456"),
            rol=ROLE_COMISION,
            school_id=self.school_a.id,
            election_id=None,
        )

        self.db.add_all([
            self.user_superadmin, self.user_resp_a,
            self.user_comision_a1, self.user_comision_null
        ])
        self.db.commit()

        # Helper para headers
        self.headers_superadmin = {"Authorization": f"Bearer {create_access_token({'sub': self.user_superadmin.email})}"}
        self.headers_resp_a = {"Authorization": f"Bearer {create_access_token({'sub': self.user_resp_a.email})}"}
        self.headers_comision_a1 = {"Authorization": f"Bearer {create_access_token({'sub': self.user_comision_a1.email})}"}
        self.headers_comision_null = {"Authorization": f"Bearer {create_access_token({'sub': self.user_comision_null.email})}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)

    # -------------------------------------------------------------------------
    # 1. Hallazgo S2-04: Comisión sin election_id deniega por defecto (403)
    # -------------------------------------------------------------------------
    def test_01_comision_without_election_id_denied_access_to_elections(self):
        """Comisión Electoral con election_id=None debe recibir 403 al consultar cualquier elección."""
        res_a1 = self.client.get(f"/api/elections/{self.election_a1.id}", headers=self.headers_comision_null)
        self.assertEqual(res_a1.status_code, 403, f"Esperado 403, obtenido {res_a1.status_code}: {res_a1.text}")
        self.assertIn("no asignada", res_a1.json()["detail"].lower())

        res_a2 = self.client.get(f"/api/elections/{self.election_a2.id}", headers=self.headers_comision_null)
        self.assertEqual(res_a2.status_code, 403, f"Esperado 403, obtenido {res_a2.status_code}: {res_a2.text}")

    def test_02_comision_without_election_id_lists_empty_elections(self):
        """Comisión Electoral con election_id=None no debe listar elecciones del colegio (cero lecturas fuera de ámbito)."""
        res = self.client.get("/api/elections", headers=self.headers_comision_null)
        self.assertEqual(res.status_code, 200)
        elections = res.json()
        self.assertEqual(len(elections), 0, f"Comisión sin election_id listó {len(elections)} elecciones indebidamente")

    # -------------------------------------------------------------------------
    # 2. Aislamiento entre elecciones del mismo colegio para Comisión Electoral
    # -------------------------------------------------------------------------
    def test_03_comision_assigned_to_election_a1_denied_access_to_election_a2(self):
        """Comisión asignada a Elección A1 recibe 403 al intentar acceder a Elección A2 del mismo colegio."""
        endpoints = [
            ("GET", f"/api/elections/{self.election_a2.id}"),
            ("GET", f"/api/elections/{self.election_a2.id}/candidates"),
            ("GET", f"/api/elections/{self.election_a2.id}/voters"),
            ("GET", f"/api/reports/election/{self.election_a2.id}/scrutiny"),
            ("GET", f"/api/reports/election/{self.election_a2.id}/acta-apertura/pdf"),
            ("POST", f"/api/elections/{self.election_a2.id}/abrir"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = self.client.get(path, headers=self.headers_comision_a1)
            else:
                res = self.client.post(path, headers=self.headers_comision_a1)
            self.assertEqual(
                res.status_code, 403,
                f"Falla de aislamiento: {method} {path} retornó {res.status_code} en vez de 403 para comisión de otra elección"
            )

    def test_04_comision_assigned_to_election_a1_allowed_access_to_a1_only(self):
        """Comisión asignada a Elección A1 puede acceder a A1 y su listado solo contiene A1."""
        res_detail = self.client.get(f"/api/elections/{self.election_a1.id}", headers=self.headers_comision_a1)
        self.assertEqual(res_detail.status_code, 200)

        res_list = self.client.get("/api/elections", headers=self.headers_comision_a1)
        self.assertEqual(res_list.status_code, 200)
        elections = res_list.json()
        self.assertEqual(len(elections), 1)
        self.assertEqual(elections[0]["id"], self.election_a1.id)

    # -------------------------------------------------------------------------
    # 3. Aislamiento cross-tenant de Responsable Institucional
    # -------------------------------------------------------------------------
    def test_05_responsable_cross_tenant_isolation(self):
        """Responsable de Colegio A recibe 403 al intentar acceder a Elección de Colegio B."""
        res = self.client.get(f"/api/elections/{self.election_b1.id}", headers=self.headers_resp_a)
        self.assertEqual(res.status_code, 403)

        res_list = self.client.get("/api/elections", headers=self.headers_resp_a)
        self.assertEqual(res_list.status_code, 200)
        elections = res_list.json()
        school_ids = {e["school_id"] for e in elections}
        self.assertNotIn(self.school_b.id, school_ids)

    # -------------------------------------------------------------------------
    # 4. Validación de asignaciones school_id/election_id al crear usuarios
    # -------------------------------------------------------------------------
    def test_06_user_create_schema_validation(self):
        """UserCreate valida y rechaza combinaciones contradictorias de rol, school_id y election_id."""
        # 1. Comisión Electoral sin election_id -> Debe fallar
        with self.assertRaises(Exception):
            UserCreate(
                nombre="Comisión Inválida",
                email="com_bad@theogen.cl",
                password="SecurePass2026!",
                rol=ROLE_COMISION,
                school_id=1,
                election_id=None
            )

        # 2. Comisión Electoral sin school_id -> Debe fallar
        with self.assertRaises(Exception):
            UserCreate(
                nombre="Comisión Inválida",
                email="com_bad2@theogen.cl",
                password="SecurePass2026!",
                rol=ROLE_COMISION,
                school_id=None,
                election_id=1
            )

        # 3. Responsable Institucional sin school_id -> Debe fallar
        with self.assertRaises(Exception):
            UserCreate(
                nombre="Resp Inválido",
                email="resp_bad@theogen.cl",
                password="SecurePass2026!",
                rol=ROLE_RESPONSABLE,
                school_id=None,
                election_id=None
            )

        # 4. Responsable Institucional con election_id -> Debe fallar
        with self.assertRaises(Exception):
            UserCreate(
                nombre="Resp Inválido",
                email="resp_bad2@theogen.cl",
                password="SecurePass2026!",
                rol=ROLE_RESPONSABLE,
                school_id=1,
                election_id=1
            )

        # 5. Superadmin con school_id o election_id -> Debe fallar
        with self.assertRaises(Exception):
            UserCreate(
                nombre="Admin Inválido",
                email="admin_bad@theogen.cl",
                password="SecurePass2026!",
                rol=ROLE_SUPERADMIN,
                school_id=1,
                election_id=None
            )

        # 6. Casos válidos
        valid_comision = UserCreate(
            nombre="Comisión Válida",
            email="com_ok@theogen.cl",
            password="SecurePass2026!",
            rol=ROLE_COMISION,
            school_id=1,
            election_id=1
        )
        self.assertEqual(valid_comision.election_id, 1)

        valid_resp = UserCreate(
            nombre="Resp Válido",
            email="resp_ok@theogen.cl",
            password="SecurePass2026!",
            rol=ROLE_RESPONSABLE,
            school_id=1,
            election_id=None
        )
        self.assertEqual(valid_resp.school_id, 1)

    # -------------------------------------------------------------------------
    # 5. Contención PII: Bloqueo seguro en producción de mutaciones destructivas
    # -------------------------------------------------------------------------
    def test_07_pii_destructive_endpoints_fail_safe_in_production(self):
        """En entorno de producción sin opt-in explícito, las mutaciones de anonimización/purga se bloquean (403)."""
        original_env = settings.ENVIRONMENT
        original_unlocked = getattr(settings, "PII_OPERATIONS_MUTATIONS_ENABLED", False)
        try:
            settings.ENVIRONMENT = "production"
            settings.PII_OPERATIONS_MUTATIONS_ENABLED = False

            # Anonimización manual debe fallar con 403 y mensaje explicativo
            res_anon = self.client.post(
                f"/api/admin/pii/anonymize-election/{self.election_a1.id}",
                headers=self.headers_superadmin
            )
            self.assertEqual(res_anon.status_code, 403)
            self.assertIn("deshabilitadas", res_anon.json()["detail"].lower())

            # Purga de auditoría manual debe fallar con 403 y mensaje explicativo
            res_purge = self.client.post(
                "/api/admin/pii/purge-audit-logs",
                headers=self.headers_superadmin
            )
            self.assertEqual(res_purge.status_code, 403)
            self.assertIn("deshabilitadas", res_purge.json()["detail"].lower())

            # Sin embargo, dry_run=true debe funcionar y reportar simulación sin alterar registros
            res_dry = self.client.post(
                f"/api/admin/pii/anonymize-election/{self.election_a1.id}?dry_run=true",
                headers=self.headers_superadmin
            )
            self.assertIn(res_dry.status_code, [200, 409])
            if res_dry.status_code == 200:
                self.assertTrue(res_dry.json().get("dry_run"))

            # Consultas de lectura/status deben permanecer operativas (200)
            res_status = self.client.get("/api/admin/pii/status", headers=self.headers_superadmin)
            self.assertEqual(res_status.status_code, 200)

            res_ready = self.client.get(
                "/api/admin/pii/elections-ready-for-anonymization",
                headers=self.headers_superadmin
            )
            self.assertEqual(res_ready.status_code, 200)

        finally:
            settings.ENVIRONMENT = original_env
            settings.PII_OPERATIONS_MUTATIONS_ENABLED = original_unlocked


if __name__ == "__main__":
    unittest.main()
