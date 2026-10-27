import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, Base, SessionLocal
from app.seed_data import seed_initial_data
from app.models import School, Election, Voter, Candidate, User

def test_everything():
    print("1. Creando tablas en base de datos...")
    Base.metadata.create_all(bind=engine)
    print("Tablas creadas con éxito.")
    
    print("2. Ejecutando seed de datos...")
    db = SessionLocal()
    seed_initial_data(db)
    
    print("3. Verificando registros creados...")
    schools_count = db.query(School).count()
    elections_count = db.query(Election).count()
    voters_count = db.query(Voter).count()
    candidates_count = db.query(Candidate).count()
    users_count = db.query(User).count()
    
    print(f"Colegios: {schools_count}")
    print(f"Elecciones: {elections_count}")
    print(f"Electores: {voters_count}")
    print(f"Candidatos: {candidates_count}")
    print(f"Usuarios: {users_count}")
    
    first_election = db.query(Election).first()
    print(f"Elección de prueba: '{first_election.nombre}' - Estado: {first_election.estado}")
    
    first_voter = db.query(Voter).first()
    print(f"Elector de prueba: {first_voter.nombre} (RUT: {first_voter.rut}) - Token: {first_voter.token_votacion}")
    
    db.close()
    print("TODO EL BACKEND Y SEED FUNCIONAN PERFECTAMENTE!")

if __name__ == "__main__":
    test_everything()
