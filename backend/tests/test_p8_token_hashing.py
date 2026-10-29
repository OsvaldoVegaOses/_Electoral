import os
import sys
import uuid
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from app.config import settings
from app.database import Base, get_db
from app.models import User, School, Election, Candidate, Voter, VotingEntitlement, Vote
from app.entitlements import derive_entitlement_key
from app.auth import get_password_hash, create_access_token, hash_voting_token, ROLE_SUPERADMIN

# In-memory SQLite for isolated testing
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


class TestP8TokenHashingAndCredentialConsumption(unittest.TestCase):
    """
    Batería de pruebas automatizadas para P8:
    - Derivación criptográfica HMAC-SHA256 para tokens de votación
    - Almacenamiento seguro del hash en base de datos
    - Canje de voto mediante comparación de hash
    - Consumo/anulación inmediata de la credencial tras la emisión del sufragio
    - Revocación de credenciales para miembros bloqueados por regla familiar
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

        # Crear colegio y elección abierta
        self.school = School(nombre="Colegio San Ignacio P8", rbd="8888-8")
        self.db.add(self.school)
        self.db.commit()

        self.election = Election(
            nombre="Elección Directiva P8",
            tipo_votacion="Centro de Padres",
            regla_votacion="Un voto por persona",
            estado="Abierta",
            school_id=self.school.id,
            fecha_inicio=datetime.now(timezone.utc),
        )
        self.db.add(self.election)
        self.db.commit()

        # Candidato
        self.candidate = Candidate(
            nombre="Lista Única",
            cargo="Presidente",
            election_id=self.election.id
        )
        self.db.add(self.candidate)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=sqlite_engine)

    def test_01_hash_voting_token_properties(self):
        """Verifica que hash_voting_token sea determinista, seguro y genere 64 caracteres hex"""
        token1 = "3a8f803d-0ccb-48b7-89f7-d92aa4c729de"
        token2 = "b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e"

        hash1 = hash_voting_token(token1)
        hash2 = hash_voting_token(token2)

        self.assertEqual(len(hash1), 64)
        self.assertEqual(len(hash2), 64)
        self.assertNotEqual(hash1, hash2)
        # Determinismo
        self.assertEqual(hash1, hash_voting_token(token1))
        # No retorna hash para cadena vacía
        self.assertEqual(hash_voting_token(""), "")

    def test_02_vote_canje_and_token_consumption(self):
        """Verifica el flujo de canje seguro con token_hash y su posterior anulación en BD"""
        raw_token = str(uuid.uuid4())
        hashed = hash_voting_token(raw_token)

        voter = Voter(
            rut="12.345.678-9",
            rut_normalizado="12345678-9",
            nombre="Juan Prueba Hashing",
            correo="juan@demo.cl",
            token_votacion=None,  # En producción el texto plano NO se almacena
            token_hash=hashed,    # Solo el hash reside en la BD
            estado="Pendiente",
            election_id=self.election.id
        )
        self.db.add(voter)
        self.db.add(VotingEntitlement(election_id=self.election.id,
                                     unit_key=derive_entitlement_key(self.election.id, "RUT:123456789")))
        self.db.commit()

        # 1. Validar el token con la credencial en texto plano que tiene el elector
        val_res = self.client.post("/api/voting/validate-token", json={"token": raw_token})
        self.assertEqual(val_res.status_code, 200)
        self.assertTrue(val_res.json()["valido"])

        # 2. Emitir voto
        submit_res = self.client.post("/api/voting/submit", json={
            "token": raw_token,
            "candidate_id": self.candidate.id
        })
        self.assertEqual(submit_res.status_code, 200)
        receipt = submit_res.json()
        self.assertIn("hash_integridad", receipt)

        # 3. Verificar que en la base de datos la credencial quedó consumida (anulada)
        self.db.refresh(voter)
        self.assertEqual(voter.estado, "Votó")
        self.assertIsNone(voter.token_hash)
        self.assertIsNone(voter.token_votacion)

        # 4. Intentar votar nuevamente con la misma credencial debe ser rechazado
        re_res = self.client.post("/api/voting/submit", json={
            "token": raw_token,
            "candidate_id": self.candidate.id
        })
        self.assertEqual(re_res.status_code, 400)

    def test_03_family_rule_revokes_sibling_tokens(self):
        """Verifica que cuando un apoderado sufraga, los tokens de la familia se anulen en BD"""
        self.election.regla_votacion = "Un voto por familia"
        self.db.commit()

        token_madre = str(uuid.uuid4())
        token_padre = str(uuid.uuid4())

        madre = Voter(
            rut="15.111.222-3",
            rut_normalizado="15111222-3",
            nombre="Madre Familia",
            familia_id="FAM-TEST-01",
            token_hash=hash_voting_token(token_madre),
            estado="Pendiente",
            election_id=self.election.id
        )
        padre = Voter(
            rut="14.333.444-5",
            rut_normalizado="14333444-5",
            nombre="Padre Familia",
            familia_id="FAM-TEST-01",
            token_hash=hash_voting_token(token_padre),
            estado="Pendiente",
            election_id=self.election.id
        )
        self.db.add_all([madre, padre])
        self.db.add(VotingEntitlement(election_id=self.election.id,
                                     unit_key=derive_entitlement_key(self.election.id, "FAM:FAM-TEST-01")))
        self.db.commit()

        # Madre emite sufragio
        res = self.client.post("/api/voting/submit", json={
            "token": token_madre,
            "candidate_id": self.candidate.id
        })
        self.assertEqual(res.status_code, 200)

        # Comprobar estado en BD
        self.db.refresh(madre)
        self.db.refresh(padre)

        self.assertEqual(madre.estado, "Votó")
        self.assertIsNone(madre.token_hash)

        # Padre queda bloqueado y su credencial fue revocada
        self.assertEqual(padre.estado, "Bloqueado")
        self.assertIsNone(padre.token_hash)

        # Intentar validar o votar con el token del padre es rechazado
        val_padre = self.client.post("/api/voting/validate-token", json={"token": token_padre})
        self.assertFalse(val_padre.json()["valido"])


if __name__ == "__main__":
    unittest.main()
