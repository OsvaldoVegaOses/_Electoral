"""Family roster preparation via the real API, with no remote provider or mail."""
import csv
import io
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from app.auth import ROLE_COMISION, get_current_user
from app.config import settings
from app.database import Base, get_db
from app.models import BeleniosBinding, Election, School, User, Voter

HEADERS=['RUT','Nombre','Curso','Correo','Familia ID']
ROWS=[['12.345.678-5','Persona ficticia A','1A','a@example.test','007'],
      ['16.234.567-2','Persona ficticia B','2A','b@example.test','007'],
      ['11.111.111-1','Persona ficticia C','1B','c@example.test','008']]


@pytest.fixture
def roster(monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    school=School(nombre='Institucion ficticia de padron')
    db.add(school);db.flush()
    election=Election(nombre='Padron familiar sintetico',school_id=school.id,motor='belenios',
                      estado='Borrador',regla_votacion='Un voto por familia')
    db.add(election);db.flush()
    user=User(nombre='Comision ficticia',email='comision@example.test',password_hash='unused',
              rol=ROLE_COMISION,school_id=school.id,election_id=election.id)
    db.add(user);db.commit()
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    monkeypatch.setattr(settings,'BELENIOS_MODE','off')
    monkeypatch.setattr(settings,'BREVO_DELIVERY_ENABLED',False)
    previous=app.dependency_overrides.copy()
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_current_user]=lambda:user
    client=TestClient(app)
    try:
        yield SimpleNamespace(db=db,client=client,election=election,user=user,
            url=f'/api/elections/{election.id}/voters/upload-excel')
    finally:
        client.close();app.dependency_overrides.clear();app.dependency_overrides.update(previous)
        db.close();engine.dispose()


def csv_bytes(rows=ROWS,headers=HEADERS,delimiter=',',bom=False):
    output=io.StringIO();writer=csv.writer(output,delimiter=delimiter)
    writer.writerow(headers);writer.writerows(rows)
    return output.getvalue().encode('utf-8-sig' if bom else 'utf-8')


def upload(roster,data,filename='padron-sintetico.csv'):
    return roster.client.post(roster.url,files={'file':(filename,data,'application/octet-stream')})


@pytest.mark.parametrize('delimiter,bom',[(',',False),(';',True),('\t',False)])
def test_csv_formats_keep_two_family_units_without_issuing_tokens(roster,delimiter,bom):
    response=upload(roster,csv_bytes(delimiter=delimiter,bom=bom))
    assert response.status_code==200,response.text
    assert response.json()['insertados']==3 and response.json()['total_errores']==0
    voters=roster.db.query(Voter).order_by(Voter.id).all()
    assert [row.familia_id for row in voters]==['007','007','008']
    assert len({row.familia_id for row in voters})==2
    assert all(row.token_hash is None and row.token_votacion is None for row in voters)
    duplicate=upload(roster,csv_bytes(delimiter=delimiter,bom=bom)).json()
    assert duplicate['insertados']==0 and duplicate['total_errores']==3
    assert roster.db.query(Voter).count()==3


def test_xlsx_upload_keeps_family_ids_and_leading_zeroes(roster):
    output=io.BytesIO()
    pd.DataFrame(ROWS,columns=HEADERS).to_excel(output,index=False)
    response=upload(roster,output.getvalue(),'padron-sintetico.xlsx')
    assert response.status_code==200 and response.json()['insertados']==3
    assert {row.familia_id for row in roster.db.query(Voter)}=={'007','008'}


def test_missing_family_column_rejects_the_file_without_inserting_people(roster):
    response=upload(roster,csv_bytes([row[:-1] for row in ROWS],HEADERS[:-1]))
    assert response.status_code==400 and 'Familia ID' in response.json()['detail']
    assert roster.db.query(Voter).count()==0


def test_missing_family_row_is_reported_and_can_be_corrected(roster):
    invalid=[*ROWS[0][:-1],'   ']
    response=upload(roster,csv_bytes([invalid,ROWS[1],ROWS[2]]))
    result=response.json()
    assert response.status_code==200 and result['insertados']==2 and result['total_errores']==1
    assert result['errores'][0]['fila']==2 and 'Familia ID' in result['errores'][0]['motivo']
    corrected=upload(roster,csv_bytes([ROWS[0]]))
    assert corrected.json()['insertados']==1 and roster.db.query(Voter).count()==3


def test_person_rule_still_accepts_a_roster_without_family_column(roster):
    roster.election.regla_votacion='Un voto por persona';roster.db.commit()
    response=upload(roster,csv_bytes([row[:-1] for row in ROWS],HEADERS[:-1]))
    assert response.status_code==200 and response.json()['insertados']==3


@pytest.mark.parametrize('restriction',['closed','bound','other_school'])
def test_upload_respects_frozen_rosters_and_institutional_access(roster,restriction):
    if restriction=='closed':roster.election.estado='Abierta'
    elif restriction=='bound':
        roster.db.add(BeleniosBinding(election_id=roster.election.id,reference='f'*32,policy='R2',phase='Draft',
            approval_ref='synthetic',draft_json='{}',total_people=0,total_units=0))
    else:roster.user.school_id=999
    roster.db.commit()
    response=upload(roster,csv_bytes())
    assert response.status_code==(403 if restriction=='other_school' else 409)
    assert roster.db.query(Voter).count()==0
