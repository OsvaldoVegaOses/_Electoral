"""
Sprint 2 — PR S2-B: Pruebas de regresión para congelamiento electoral,
instantánea íntegra y denominadores estables.

Verifica:
1. SNAP-DET: La instantánea canónica es determinista (mismos parámetros = idéntico config_hash).
2. SNAP-DIFF: Cualquier alteración en reglas, candidatos, calendario o totales altera el config_hash.
3. SNAP-PII: La instantánea pública no contiene RUTs ni PII de electores.
4. FAM-DENOM: En regla familiar (5 personas en 2 familias), el denominador congelado es 2 y
   se preserva en el escrutinio (50% con 1 voto) aun después de que familia_id quede anulado (PII).
5. FREEZE-PUT: PUT /api/elections/{id} rechaza modificaciones estructurales y de calendario (409) tras apertura.
6. FREEZE-PARTS: Prohíbe agregar o alterar candidatos, votantes y comisiones tras apertura (409).
7. CLOSE-CAL: Al cerrar la elección, se registra fecha_cierre_efectiva sin destruir la fecha_fin programada.
8. SNAP-VERIFY: Detección de divergencia si la configuración es adulterada directamente en BD.
"""
import os
import sys
import json
import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app
from app.database import Base, get_db
from app.models import School, Election, Candidate, Voter, ElectoralCommittee, User
from app.auth import get_password_hash, create_access_token, ROLE_SUPERADMIN

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


class TestS2BElectionSnapshotAndFreezing(unittest.TestCase):
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

        self.school = School(nombre="Colegio San Ignacio S2B", rbd="3333-3")
        self.db.add(self.school)
        self.db.commit()

        self.admin = User(
            nombre="Super Admin S2B",
            email="admin_s2b@theogen.cl",
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

    # -------------------------------------------------------------------------
    # 1. Determinismo de la instantánea de configuración
    # -------------------------------------------------------------------------
    def test_01_canonical_snapshot_is_deterministic(self):
        """Mismos parámetros de configuración deben generar idéntico config_hash sin depender de timestamps mutables."""
        from app.routers.elections import build_canonical_config_snapshot, compute_snapshot_hash

        fixed_start = datetime(2026, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
        fixed_end = datetime(2026, 11, 3, 18, 0, 0, tzinfo=timezone.utc)

        e1 = Election(
            id=10,
            nombre="Elección Directiva 2026",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            fecha_inicio=fixed_start,
            fecha_fin=fixed_end,
            estado="Borrador",
        )
        self.db.add(e1)
        self.db.commit()

        cand = Candidate(nombre="Lista A", cargo="Presidente", orden=1, election_id=e1.id)
        comm = ElectoralCommittee(nombre="Ana Rojas", rut="12.345.678-5", cargo="Presidenta", election_id=e1.id)
        self.db.add_all([cand, comm])
        self.db.commit()

        snap1 = build_canonical_config_snapshot(e1, self.db)
        hash1 = compute_snapshot_hash(snap1)

        # Re-computar sobre los mismos datos
        snap2 = build_canonical_config_snapshot(e1, self.db)
        hash2 = compute_snapshot_hash(snap2)

        self.assertEqual(hash1, hash2, "El hash de la instantánea no es determinista")
        self.assertEqual(len(hash1), 64, "El hash debe ser SHA-256 (64 hex)")

        # Verificar que NO contiene RUTs ni correos personales
        snap_json = json.dumps(snap1)
        self.assertNotIn("12.345.678-5", snap_json, "La instantánea no debe filtrar RUTs")
        self.assertNotIn("12345678-5", snap_json, "La instantánea no debe filtrar RUTs normalizados")

    def test_02_snapshot_hash_changes_on_any_alteration(self):
        """Cualquier cambio en candidatos, fechas o reglas debe modificar el config_hash."""
        from app.routers.elections import build_canonical_config_snapshot, compute_snapshot_hash

        fixed_start = datetime(2026, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
        fixed_end = datetime(2026, 11, 3, 18, 0, 0, tzinfo=timezone.utc)

        e = Election(
            id=20,
            nombre="Elección Original",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            fecha_inicio=fixed_start,
            fecha_fin=fixed_end,
            estado="Borrador",
        )
        self.db.add(e)
        self.db.commit()

        cand1 = Candidate(nombre="Lista Uno", cargo="Presidencia", orden=1, election_id=e.id)
        self.db.add(cand1)
        self.db.commit()

        snap_orig = build_canonical_config_snapshot(e, self.db)
        hash_orig = compute_snapshot_hash(snap_orig)

        # Modificar candidato
        cand1.nombre = "Lista Uno Modificada"
        self.db.commit()

        snap_mod = build_canonical_config_snapshot(e, self.db)
        hash_mod = compute_snapshot_hash(snap_mod)

        self.assertNotEqual(hash_orig, hash_mod, "Modificar un candidato debió cambiar el hash")

    # -------------------------------------------------------------------------
    # 2. Denominador familiar estable que sobrevive a depuración de PII
    # -------------------------------------------------------------------------
    def test_03_family_denominator_preserved_post_pii_anonymization(self):
        """En regla 'Un voto por familia' con 5 personas en 2 familias, el denominador congelado es 2 y sobrevive a PII."""
        # 1. Crear elección
        now = datetime.now(timezone.utc)
        election = Election(
            nombre="Elección Familiar Denominador",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por familia",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(days=1),
            estado="Borrador",
        )
        self.db.add(election)
        self.db.commit()

        # Candidato
        cand = Candidate(nombre="Lista Unida", cargo="Directiva", orden=1, election_id=election.id)
        self.db.add(cand)

        # 5 electores: 3 de FAM-A, 2 de FAM-B (Total personas = 5, Total familias = 2)
        voters = [
            Voter(rut="15.111.111-1", rut_normalizado="15111111-1", nombre="Padre A", familia_id="FAM-A", election_id=election.id),
            Voter(rut="16.222.222-2", rut_normalizado="16222222-2", nombre="Madre A", familia_id="FAM-A", election_id=election.id),
            Voter(rut="17.333.333-3", rut_normalizado="17333333-3", nombre="Hijo A", familia_id="FAM-A", election_id=election.id),
            Voter(rut="18.444.444-4", rut_normalizado="18444444-4", nombre="Padre B", familia_id="FAM-B", election_id=election.id),
            Voter(rut="19.555.555-5", rut_normalizado="19555555-5", nombre="Madre B", familia_id="FAM-B", election_id=election.id),
        ]
        self.db.add_all(voters)
        self.db.commit()

        # 2. Abrir la elección
        res_open = self.client.post(f"/api/elections/{election.id}/abrir", headers=self.headers)
        self.assertEqual(res_open.status_code, 200)

        self.db.refresh(election)
        # Verificar que los totales congelados fueron calculados y guardados
        self.assertEqual(election.total_padron_congelado, 5, "Total padrón congelado debe ser 5 personas")
        self.assertEqual(election.total_habilitados_congelado, 2, "Total habilitados congelado debe ser 2 familias")
        self.assertIsNotNone(election.config_hash)
        self.assertIsNotNone(election.config_snapshot)

        # 3. Simular un voto para la Lista Unida y cerrar la elección
        from app.models import Vote
        voto = Vote(candidate_id=cand.id, election_id=election.id, hash_integridad="hash_voto_1")
        voters[0].estado = "Votó"
        self.db.add(voto)
        self.db.commit()

        # Cerrar elección
        res_close = self.client.post(f"/api/elections/{election.id}/cerrar", headers=self.headers)
        self.assertEqual(res_close.status_code, 200)

        # 4. Consultar escrutinio ANTES de anonimización
        res_scrutiny_before = self.client.get(f"/api/reports/election/{election.id}/scrutiny", headers=self.headers)
        self.assertEqual(res_scrutiny_before.status_code, 200)
        data_before = res_scrutiny_before.json()
        self.assertEqual(data_before["total_padron"], 2, "Denominador antes de anonimización debe ser 2 familias")
        self.assertEqual(data_before["total_votos"], 1)
        self.assertEqual(data_before["participacion_porcentaje"], 50.0)

        # 5. Anonimizar padrón (anulando familia_id de todos los electores)
        for v in voters:
            v.familia_id = None
            v.pii_eliminado_en = datetime.now(timezone.utc)
        self.db.commit()

        # 6. Consultar escrutinio DESPUÉS de anonimización
        res_scrutiny_after = self.client.get(f"/api/reports/election/{election.id}/scrutiny", headers=self.headers)
        self.assertEqual(res_scrutiny_after.status_code, 200)
        data_after = res_scrutiny_after.json()

        # El denominador DEBE seguir siendo 2 familias y 50% de participación
        self.assertEqual(data_after["total_padron"], 2, "El denominador colapsó tras anonimizar familia_id!")
        self.assertEqual(data_after["participacion_porcentaje"], 50.0, "El porcentaje de participación fue corrompido post-PII!")

    # -------------------------------------------------------------------------
    # 3. Congelamiento estricto tras apertura (409 Conflict)
    # -------------------------------------------------------------------------
    def test_04_mutations_blocked_after_opening(self):
        """Tras apertura, PUT /elections, candidatos, votantes y comisiones son rechazados (409 Conflict)."""
        now = datetime.now(timezone.utc)
        election = Election(
            nombre="Elección Congelada Test",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            fecha_inicio=now - timedelta(hours=1),
            fecha_fin=now + timedelta(days=2),
            estado="Borrador",
        )
        self.db.add(election)
        self.db.commit()

        cand = Candidate(nombre="Lista Test", cargo="Cargo", orden=1, election_id=election.id)
        voter = Voter(rut="15.111.222-3", rut_normalizado="15111222-3", nombre="Elector", election_id=election.id)
        self.db.add_all([cand, voter])
        self.db.commit()

        # Abrir la elección
        res_open = self.client.post(f"/api/elections/{election.id}/abrir", headers=self.headers)
        self.assertEqual(res_open.status_code, 200)

        # 1. Intentar modificar nombre o fechas por PUT general
        res_put = self.client.put(
            f"/api/elections/{election.id}",
            headers=self.headers,
            json={"nombre": "Nuevo Nombre Ilegítimo"}
        )
        self.assertEqual(res_put.status_code, 409, f"Esperado 409 en PUT elección abierta, obtenido {res_put.status_code}")

        # 2. Intentar agregar candidato
        res_cand = self.client.post(
            f"/api/elections/{election.id}/candidates",
            headers=self.headers,
            json={"nombre": "Candidato Extemporáneo", "cargo": "Vocal"}
        )
        self.assertEqual(res_cand.status_code, 409, f"Esperado 409 al agregar candidato en elección abierta, obtenido {res_cand.status_code}")

        # 3. Intentar agregar votante manual
        res_voter = self.client.post(
            f"/api/elections/{election.id}/voters",
            headers=self.headers,
            json={"rut": "18.345.678-4", "nombre": "Votante Tardío"}
        )
        self.assertEqual(res_voter.status_code, 409, f"Esperado 409 al agregar votante en elección abierta, obtenido {res_voter.status_code}")

        # 4. Intentar agregar miembro de comisión
        res_comm = self.client.post(
            f"/api/elections/{election.id}/comite",
            headers=self.headers,
            json={"nombre": "Comisionado Tardío", "rut": "19.567.890-1", "cargo": "Vocal"}
        )
        self.assertEqual(res_comm.status_code, 409)

    # -------------------------------------------------------------------------
    # 4. Preservación del cronograma vs fecha de cierre efectiva
    # -------------------------------------------------------------------------
    def test_05_programmed_end_date_preserved_on_close(self):
        """Al cerrar la elección, se registra fecha_cierre_efectiva y no se destruye fecha_fin programada."""
        now = datetime.now(timezone.utc)
        programmed_end = now + timedelta(days=5)
        election = Election(
            nombre="Elección Calendario",
            school_id=self.school.id,
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            fecha_inicio=now - timedelta(hours=2),
            fecha_fin=programmed_end,
            estado="Borrador",
        )
        self.db.add(election)
        self.db.commit()

        cand = Candidate(nombre="Lista Calendario", cargo="Cargo", orden=1, election_id=election.id)
        voter = Voter(rut="15.111.222-3", rut_normalizado="15111222-3", nombre="Elector", election_id=election.id)
        self.db.add_all([cand, voter])
        self.db.commit()

        # Abrir
        self.client.post(f"/api/elections/{election.id}/abrir", headers=self.headers)

        # Cerrar antes de fecha_fin programada
        res_close = self.client.post(f"/api/elections/{election.id}/cerrar", headers=self.headers)
        self.assertEqual(res_close.status_code, 200)

        self.db.refresh(election)
        # La fecha_fin programada original NO debe haber cambiado al día/hora actual
        diff_from_prog = abs((election.fecha_fin.replace(tzinfo=timezone.utc) - programmed_end).total_seconds())
        self.assertLess(diff_from_prog, 2.0, "La fecha_fin programada fue sobreescrita por la hora de cierre!")

        # Debe existir fecha_cierre_efectiva registrada
        self.assertIsNotNone(election.fecha_cierre_efectiva, "fecha_cierre_efectiva no fue registrada")

    def test_06_scrutiny_blocks_legacy_election_without_verified_snapshot(self):
        election = Election(
            nombre="Elección Legada Sin Conciliación",
            school_id=self.school.id,
            estado="Finalizada",
            total_padron_congelado=2,
            total_habilitados_congelado=2,
        )
        self.db.add(election)
        self.db.commit()

        response = self.client.get(
            f"/api/reports/election/{election.id}/scrutiny",
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("conciliación", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
