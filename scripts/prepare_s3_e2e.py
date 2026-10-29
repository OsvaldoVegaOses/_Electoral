"""Deterministic fictitious fixtures on an explicitly disposable, migrated database."""
import json
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from sqlalchemy.engine import make_url

def main():
    from app.config import settings
    from app.database import SessionLocal
    from app.models import School,Election,User,Voter,Candidate
    from app.auth import get_password_hash,hash_voting_token,ROLE_SUPERADMIN,ROLE_COMISION,ROLE_RESPONSABLE
    from app.rut_validator import format_rut
    from uuid import uuid4
    url=make_url(settings.DATABASE_URL)
    if settings.ENVIRONMENT!='test' or not url.database or not url.database.startswith('s3_'):
        raise RuntimeError('Fixtures require ENVIRONMENT=test and a dedicated s3_ database')
    password=os.environ['E2E_ADMIN_PASSWORD']
    email=os.environ.get('E2E_ADMIN_EMAIL','s3-admin@example.org')
    if len(password)<16:raise RuntimeError('Synthetic E2E password required')
    from datetime import datetime,timedelta,timezone
    with SessionLocal() as db:
        if db.query(User).filter_by(email=email).first():raise RuntimeError('Fixture database already populated; use a new disposable database')
        first,other=School(nombre='S3 Synthetic A'),School(nombre='S3 Synthetic B')
        admin=User(nombre='Administrador General',email=email,password_hash=get_password_hash(password),rol=ROLE_SUPERADMIN)
        db.add_all([first,other,admin]);db.flush()
        family=Election(nombre='S3 E2E Family',school_id=first.id,regla_votacion='Un voto por familia',estado='Borrador',
                        fecha_inicio=datetime.now(timezone.utc)-timedelta(minutes=1),fecha_fin=datetime.now(timezone.utc)+timedelta(days=1),motor='mvp')
        belenios=Election(nombre='S3 E2E Belenios',school_id=first.id,regla_votacion='Un voto por familia',motor='belenios',estado='Borrador')
        foreign=Election(nombre='S3 E2E Other School',school_id=other.id,estado='Borrador')
        db.add_all([family,belenios,foreign]);db.flush()
        commission=User(nombre='S3 Commission',email='s3-commission@example.org',rol=ROLE_COMISION,school_id=first.id,
                        election_id=family.id,password_hash=get_password_hash(password))
        unassigned=User(nombre='S3 Unassigned',email='s3-unassigned@example.org',rol=ROLE_COMISION,school_id=first.id,
                        election_id=None,password_hash=get_password_hash(password))
        db.add_all([commission,unassigned])
        tokens=[secrets.token_urlsafe(32) for _ in range(3)]
        voters=[]
        for index,(rut,family_id) in enumerate([('12345678-5','FAMILY-A'),('16234567-2','FAMILY-A'),('11111111-1','FAMILY-B')]):
            voter=Voter(election_id=family.id,nombre=f'S3 Synthetic {index}',rut=format_rut(rut),rut_normalizado=rut.replace('-',''),
                        familia_id=family_id,correo=f's3-controlled-{index}@example.org',token_hash=hash_voting_token(tokens[index]),token_votacion=None,estado='Pendiente')
            db.add(voter);voters.append(voter)
        options=[Candidate(election_id=family.id,nombre='S3 Lista A',orden=1),Candidate(election_id=family.id,nombre='S3 Lista B',orden=2)]
        db.add_all(options);db.flush()
        fixture={'election_id':family.id,'other_election_id':foreign.id,'belenios_election_id':belenios.id,
                 'school_id':first.id,'candidate_id':options[0].id,'tokens':tokens,
                 'commission_email':commission.email,'unassigned_email':unassigned.email}
        db.commit()
    output=Path(os.environ.get('S3_E2E_FIXTURES_FILE','../.runtime/e2e-fixtures.json')).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(fixture),encoding='utf-8')
    print('Synthetic fixtures prepared; tokens and passwords omitted')

if __name__=='__main__':main()
