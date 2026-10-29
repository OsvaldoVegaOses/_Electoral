from types import SimpleNamespace
from uuid import uuid4
import json
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import brevo, credentials
from app.auth import create_access_token, hash_voting_token, ROLE_SUPERADMIN
from app.config import settings
from app.database import Base, get_db
from app.models import School, Election, Voter, User, CredentialDelivery, BeleniosBinding
from main import app

@pytest.fixture
def context(monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool,connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    db=Session()
    school=School(nombre='S3 synthetic')
    user=User(nombre='Synthetic',email='s3-admin@example.test',rol=ROLE_SUPERADMIN,password_hash='unused')
    db.add_all([school,user]);db.flush()
    election=Election(nombre='S3 synthetic',school_id=school.id,estado='Borrador')
    db.add(election);db.flush()
    voter=Voter(election_id=election.id,rut='12345678-5',rut_normalizado='123456785',nombre='Synthetic',
                correo='controlled@example.test',estado='Pendiente',token_hash=hash_voting_token('previous-token'))
    db.add(voter);db.commit()
    monkeypatch.setattr(settings,'ENVIRONMENT','test')
    previous=app.dependency_overrides.copy()
    def get_test_db():
        yield db
    app.dependency_overrides[get_db]=get_test_db
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer '+create_access_token({'sub':user.email})
        yield SimpleNamespace(db=db,election=election,voter=voter,school=school,client=client)
    app.dependency_overrides.clear();app.dependency_overrides.update(previous)
    db.close();engine.dispose()

def test_acceptance_never_activates_or_persists_clear_token(context):
    captured=[]
    def sender(recipient,token,key):
        captured.append(token)
        return brevo.AcceptedMessage('test-message')
    operation=credentials.issue(context.db,context.voter,context.election,uuid4(),sender=sender)
    assert operation.status=='ACCEPTED'
    assert context.voter.token_hash==hash_voting_token('previous-token')
    assert context.voter.token_votacion is None
    values=context.db.execute(text('SELECT * FROM credential_deliveries')).all()
    assert captured[0] not in str(values)
    with pytest.raises(HTTPException) as rejected:
        credentials.reconcile(context.db,operation,context.voter,context.election,checker=lambda *args:None)
    assert rejected.value.status_code==409
    credentials.reconcile(context.db,operation,context.voter,context.election,checker=lambda *args:'test-message')
    assert operation.status=='DELIVERED' and operation.active_slot is None
    assert context.voter.token_hash==hash_voting_token(captured[0])
    assert context.voter.token_votacion is None

def test_unknown_preserves_previous_and_blocks_duplicate(context):
    def lost(*args):
        raise brevo.DeliveryUnknown('timeout')
    operation=credentials.issue(context.db,context.voter,context.election,uuid4(),sender=lost)
    assert operation.status=='UNKNOWN'
    with pytest.raises(HTTPException) as blocked:
        credentials.issue(context.db,context.voter,context.election,uuid4(),sender=lost)
    assert blocked.value.status_code==409
    assert context.voter.token_hash==hash_voting_token('previous-token')
    assert context.db.query(CredentialDelivery).count()==1

def test_rejected_allows_explicit_new_operation_but_never_reuses_id(context):
    def rejected(*args):
        raise brevo.DeliveryRejected('rejected')
    key=uuid4()
    operation=credentials.issue(context.db,context.voter,context.election,key,sender=rejected)
    assert operation.status=='REJECTED' and operation.active_slot is None
    with pytest.raises(HTTPException):
        credentials.issue(context.db,context.voter,context.election,key,sender=rejected)
    context.election.estado='Abierta';context.db.commit()
    with pytest.raises(HTTPException):
        credentials.reconcile(context.db,operation,context.voter,context.election,checker=lambda *args:'message')

def test_roster_belenios_production_never_issues_mvp_tokens(context,monkeypatch):
    monkeypatch.setattr(settings,'ENVIRONMENT','production')
    context.election.motor='belenios';context.db.commit()
    response=context.client.post(f'/api/elections/{context.election.id}/voters',json={'nombre':'Synthetic new','rut':'16.234.567-2'})
    assert response.status_code==201,response.text
    created=context.db.get(Voter,response.json()['id'])
    assert created.token_hash is None and created.token_votacion is None
    assert context.client.post(f'/api/elections/{context.election.id}/abrir').status_code==409

def test_dashboard_distinguishes_unverified_and_verified_belenios(context):
    binding=BeleniosBinding(election_id=context.election.id,reference=uuid4().hex,policy='R2',phase='Tallied',
                           draft_json='{}',approval_ref='synthetic',total_people=1,total_units=1)
    context.db.add(binding);context.db.commit()
    response=context.client.get('/api/reports/dashboard-stats')
    assert response.status_code==200,response.text
    assert response.json()['total_votos_emitidos'] is None and response.json()['resultados_pendientes']==1
    assert context.client.get(f'/api/elections/{context.election.id}/belenios/record/pdf').status_code==409
    binding.phase='Verified';binding.verified_result=json.dumps({'counted_ballots':1,'options':[{'label':'Synthetic <option>','votes':1}]})
    context.db.commit()
    response=context.client.get('/api/reports/dashboard-stats')
    assert response.json()['total_votos_emitidos']==1
    pdf=context.client.get(f'/api/elections/{context.election.id}/belenios/record/pdf')
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    assert pdf.headers['cache-control']=='no-store'

@pytest.mark.parametrize('mismatch',['recipient','tag','id'])
def test_delivery_confirmation_rejects_mismatched_provider_event(monkeypatch,mismatch):
    from pydantic import SecretStr
    key=str(uuid4())
    monkeypatch.setattr(settings,'BREVO_DELIVERY_ENABLED',True)
    monkeypatch.setattr(settings,'BREVO_API_KEY',SecretStr('synthetic'))
    event={'event':'delivered','email':'recipient@example.test','tag':'theogen-'+key,'messageId':'id-1'}
    event[{'recipient':'email','tag':'tag','id':'messageId'}[mismatch]]='different'
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'events':[event]}))
    assert brevo.confirmed_delivery('recipient@example.test',key,'id-1',transport=transport) is None

def test_confirmation_requires_matching_delivery_event(monkeypatch):
    from pydantic import SecretStr
    key=str(uuid4())
    monkeypatch.setattr(settings,'BREVO_DELIVERY_ENABLED',True)
    monkeypatch.setattr(settings,'BREVO_API_KEY',SecretStr('synthetic'))
    event={'event':'delivered','email':'recipient@example.test','tag':'theogen-'+key,'messageId':'id-1'}
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'events':[event]}))
    assert brevo.confirmed_delivery('recipient@example.test',key,'id-1',transport=transport)=='id-1'

def test_issue_refreshes_election_before_sending(context):
    assert context.election.estado=='Borrador'
    context.db.execute(text("UPDATE elections SET estado='Abierta' WHERE id=:id"),{'id':context.election.id})
    sent=[]
    with pytest.raises(HTTPException) as blocked:
        credentials.issue(context.db,context.voter,context.election,uuid4(),sender=lambda *args:sent.append(args))
    assert blocked.value.status_code==409
    assert sent==[] and context.db.query(CredentialDelivery).count()==0

def test_reconcile_refreshes_operation_and_never_activates_rejected_intent(context):
    operation=credentials.issue(context.db,context.voter,context.election,uuid4(),
        sender=lambda *args:brevo.AcceptedMessage('test-message'))
    context.db.execute(text("UPDATE credential_deliveries SET status='REJECTED' WHERE id=:id"),{'id':operation.id})
    checked=[]
    with pytest.raises(HTTPException) as blocked:
        credentials.reconcile(context.db,operation,context.voter,context.election,checker=lambda *args:checked.append(args))
    assert blocked.value.status_code==409 and checked==[]
    assert context.voter.token_hash==hash_voting_token('previous-token')
