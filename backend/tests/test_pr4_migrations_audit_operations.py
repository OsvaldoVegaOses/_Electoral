import os
import io
import sys
import unittest
import subprocess
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.database import Base, get_db
from app.models import User, School, Election, Candidate, Voter, VotingEntitlement, Vote, AuditLog
from app.auth import (
    get_password_hash, create_access_token, log_audit, mask_email,
    sanitize_formula_injection, ROLE_RESPONSABLE, ROLE_SUPERADMIN
)
from app.rut_validator import mask_rut, validate_rut, format_rut, clean_rut

# In-memory SQLite for fast functional testing
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


class TestPR4PIIAndFormulaSanitization(unittest.TestCase):
    """
    Pruebas unitarias de minimización de datos (PII) y sanitización de inyección de fórmulas.
    """
    def test_mask_rut_standard_8_digits(self):
        self.assertEqual(mask_rut("16.234.567-2"), "16.***.***-2")
        self.assertEqual(mask_rut("162345672"), "16.***.***-2")
        self.assertEqual(mask_rut("16234567-2"), "16.***.***-2")

    def test_mask_rut_7_digits(self):
        self.assertEqual(mask_rut("9.876.543-K"), "9.***.***-K")
        self.assertEqual(mask_rut("9876543K"), "9.***.***-K")

    def test_mask_rut_edge_cases(self):
        self.assertEqual(mask_rut(""), "***")
        self.assertEqual(mask_rut(None), "***")
        self.assertEqual(mask_rut("12"), "***")

    def test_mask_email(self):
        self.assertEqual(mask_email("director@colegioa.cl"), "d***r@colegioa.cl")
        self.assertEqual(mask_email("ab@colegiob.cl"), "a***@colegiob.cl")
        self.assertEqual(mask_email("superadmin.general@theogen.gob.cl"), "s***l@theogen.gob.cl")

    def test_mask_email_edge_cases(self):
        self.assertEqual(mask_email(""), "***")
        self.assertEqual(mask_email(None), "***")
        self.assertEqual(mask_email("invalid-email"), "***")

    def test_sanitize_formula_injection(self):
        # DDE / Formula injection characters: '=', '+', '-', '@', '\t', '\r'
        self.assertEqual(sanitize_formula_injection("=cmd|' /C calc'!A0"), "'=cmd|' /C calc'!A0")
        self.assertEqual(sanitize_formula_injection("+SUM(A1:A10)"), "'+SUM(A1:A10)")
        self.assertEqual(sanitize_formula_injection("-100"), "'-100")
        self.assertEqual(sanitize_formula_injection("@something"), "'@something")
        self.assertEqual(sanitize_formula_injection("\talert(1)"), "'\talert(1)")
        self.assertEqual(sanitize_formula_injection("\rcommand"), "'\rcommand")

    def test_sanitize_formula_injection_benign(self):
        self.assertEqual(sanitize_formula_injection("Juan Silva"), "Juan Silva")
        self.assertEqual(sanitize_formula_injection("4° Medio B"), "4° Medio B")
        self.assertEqual(sanitize_formula_injection(None), None)


class TestPR4AtomicAudit(unittest.TestCase):
    """
    Pruebas de atomicidad en bitácora de auditoría (commit=False).
    """
    def setUp(self):
        Base.metadata.create_all(bind=sqlite_engine)
        self.db = SQLiteSessionLocal()
        self.school = School(nombre="Colegio Audit", rbd="11111", comuna="Santiago")
        self.db.add(self.school)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)

    def test_atomic_audit_rollback_on_business_failure(self):
        """Si la mutación de negocio falla y se hace rollback, la auditoría se revierte."""
        try:
            # Iniciamos una operación con audit log atómico
            log_audit(
                self.db,
                accion="Mutación de Prueba",
                detalle="Operación que fallará",
                usuario="test@colegio.cl",
                school_id=self.school.id,
                commit=False
            )
            # Simulamos fallo de negocio provocando rollback explícito
            raise RuntimeError("Error simulado en proceso de negocio")
        except RuntimeError:
            self.db.rollback()

        # Verificar que el registro de auditoría NO fue persistido
        logs = self.db.query(AuditLog).filter(AuditLog.accion == "Mutación de Prueba").all()
        self.assertEqual(len(logs), 0)

    def test_atomic_audit_commit_on_business_success(self):
        """Si la mutación de negocio es exitosa y se hace commit, la auditoría se confirma."""
        log_audit(
            self.db,
            accion="Mutación Exitosa",
            detalle="Operación que concluye con éxito",
            usuario="test@colegio.cl",
            school_id=self.school.id,
            commit=False
        )
        self.db.commit()

        logs = self.db.query(AuditLog).filter(AuditLog.accion == "Mutación Exitosa").all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].usuario, "test@colegio.cl")
        self.assertEqual(logs[0].school_id, self.school.id)


class TestPR4OperationsAndBulkUpload(unittest.TestCase):
    """
    Pruebas de operaciones: Streaming, rechazo de .xls, neutralización de fórmulas en carga masiva y PII.
    """
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=sqlite_engine)
        self.db = SQLiteSessionLocal()

        self.school = School(nombre="Colegio Operaciones", rbd="99999", comuna="Santiago")
        self.db.add(self.school)
        self.db.commit()

        self.user = User(
            email="responsable@colegio.cl",
            nombre="Responsable Colegio",
            password_hash=get_password_hash("Pass123!"),
            rol=ROLE_RESPONSABLE,
            school_id=self.school.id
        )
        self.db.add(self.user)
        self.db.commit()

        self.election = Election(
            nombre="Elección Directiva PR4",
            tipo="Directiva de Curso",
            regla_votacion="Un voto por elector",
            fecha_inicio=datetime.now(timezone.utc) - timedelta(hours=1),
            fecha_fin=datetime.now(timezone.utc) + timedelta(hours=2),
            estado="Borrador",
            school_id=self.school.id
        )
        self.db.add(self.election)
        self.db.commit()

        self.token = create_access_token({"sub": self.user.email})
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)
        app.dependency_overrides.clear()

    def test_upload_rejects_legacy_xls(self):
        """Archivos .xls legados son rechazados con 400 por motivos de seguridad."""
        fake_content = b"fake binary xls content"
        files = {
            "file": ("padron_antiguo.xls", io.BytesIO(fake_content), "application/vnd.ms-excel")
        }
        res = self.client.post(
            f"/api/elections/{self.election.id}/voters/upload-excel",
            headers=self.headers,
            files=files
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("legado no está permitido", res.json()["detail"])

    def test_upload_streaming_rejects_file_exceeding_10mb(self):
        """Archivos que exceden 10 MB se abortan en streaming con 413 sin saturar memoria."""
        # 11 MB en memoria como BytesIO
        oversized_data = b"X" * (11 * 1024 * 1024)
        files = {
            "file": ("padron_gigante.csv", io.BytesIO(oversized_data), "text/csv")
        }
        res = self.client.post(
            f"/api/elections/{self.election.id}/voters/upload-excel",
            headers=self.headers,
            files=files
        )
        self.assertEqual(res.status_code, 413)
        self.assertIn("excede el tamaño máximo permitido", res.json()["detail"])

    def test_upload_csv_sanitizes_formula_injection(self):
        """Valores con fórmulas maliciosas en CSV son neutralizados al almacenarse."""
        csv_content = (
            "RUT,Nombre,Curso,Correo,Familia ID\n"
            "16.234.567-2,=cmd|' /C calc'!A0,+CursoMalicioso,fsilva@ejemplo.cl,@FAM-101\n"
        ).encode("utf-8")

        files = {
            "file": ("padron_injection.csv", io.BytesIO(csv_content), "text/csv")
        }
        res = self.client.post(
            f"/api/elections/{self.election.id}/voters/upload-excel",
            headers=self.headers,
            files=files
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["insertados"], 1)

        # Consultar voter insertado en BD
        voter = self.db.query(Voter).filter(Voter.rut == "16.234.567-2").first()
        self.assertIsNotNone(voter)
        # Debe haberse antepuesto apóstrofe de neutralización
        self.assertTrue(voter.nombre.startswith("'="))
        self.assertTrue(voter.curso.startswith("'+"))
        self.assertTrue(voter.familia_id.startswith("'@"))

    def test_upload_preserves_leading_zeros_dtype_str(self):
        """Columnas alfanuméricas con ceros a la izquierda (ej. Familia ID '007') se preservan intactas."""
        csv_content = (
            "RUT,Nombre,Curso,Correo,Familia ID\n"
            "17.123.456-7,Camila Vergara,01A,cvergara@ejemplo.cl,007\n"
        ).encode("utf-8")

        files = {
            "file": ("padron_zeros.csv", io.BytesIO(csv_content), "text/csv")
        }
        res = self.client.post(
            f"/api/elections/{self.election.id}/voters/upload-excel",
            headers=self.headers,
            files=files
        )
        self.assertEqual(res.status_code, 200)

        voter = self.db.query(Voter).filter(Voter.rut == "17.123.456-7").first()
        self.assertIsNotNone(voter)
        self.assertEqual(voter.curso, "01A")
        self.assertEqual(voter.familia_id, "007")

    def test_create_voter_sanitizes_and_masks_pii_in_audit(self):
        """Crear votante manual neutraliza fórmulas y enmascara RUT en auditoría."""
        res = self.client.post(
            f"/api/elections/{self.election.id}/voters",
            headers=self.headers,
            json={
                "rut": "18.345.678-4",
                "nombre": "=DDE(calc)",
                "curso": "+3B",
                "correo": "test@demo.cl",
                "familia_id": "@FAM-99"
            }
        )
        self.assertEqual(res.status_code, 201)
        voter_id = res.json()["id"]

        voter = self.db.query(Voter).filter(Voter.id == voter_id).first()
        self.assertTrue(voter.nombre.startswith("'="))
        self.assertTrue(voter.curso.startswith("'+"))
        self.assertTrue(voter.familia_id.startswith("'@"))

        # Verificar auditoría con RUT enmascarado
        audit = self.db.query(AuditLog).filter(
            AuditLog.accion == "Agregó elector",
            AuditLog.school_id == self.school.id
        ).first()
        self.assertIsNotNone(audit)
        self.assertIn("18.***.***-4", audit.detalle)
        self.assertNotIn("18.345.678-4", audit.detalle)


class TestPR4AlembicOnPostgres(unittest.TestCase):
    """
    Prueba de ciclo completo de migraciones Alembic sobre PostgreSQL 16 real.
    Upgrade head -> Downgrade base -> Upgrade head.
    """
    def test_alembic_upgrade_downgrade_cycle(self):
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env = os.environ.copy()
        env["DATABASE_URL"] = "postgresql://postgres@127.0.0.1:5439/theogen_test"

        # 1. alembic upgrade head
        res_up1 = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_up1.returncode, 0, f"Error en alembic upgrade head: {res_up1.stderr}")

        # 2. alembic downgrade base
        res_down = subprocess.run(
            ["alembic", "downgrade", "base"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_down.returncode, 0, f"Error en alembic downgrade base: {res_down.stderr}")

        # 3. alembic upgrade head (re-aplicación limpia)
        res_up2 = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True
        )
        self.assertEqual(res_up2.returncode, 0, f"Error en alembic upgrade head (2nd run): {res_up2.stderr}")

        # 4. Verificar que todas las tablas existan en PostgreSQL
        pg_engine = create_engine("postgresql+psycopg2://postgres@127.0.0.1:5439/theogen_test")
        inspector = inspect(pg_engine)
        tables = inspector.get_table_names()
        expected_tables = {
            "schools", "users", "elections", "voters", "candidates",
            "votes", "electoral_committee", "audit_logs", "voting_entitlements",
            "alembic_version"
        }
        for table in expected_tables:
            self.assertIn(table, tables, f"Falta tabla '{table}' tras migración Alembic")

        # 5. Verificar índices críticos
        voters_indexes = {idx["name"] for idx in inspector.get_indexes("voters")}
        self.assertIn("ix_voters_rut_normalizado", voters_indexes)
        self.assertIn("ix_voters_token_votacion", voters_indexes)

        entitlements_indexes = {idx["name"] for idx in inspector.get_indexes("voting_entitlements")}
        self.assertIn("ix_voting_entitlements_election_unit", entitlements_indexes)
        pg_engine.dispose()


if __name__ == "__main__":
    unittest.main()
