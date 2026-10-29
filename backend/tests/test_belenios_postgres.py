"""Real PostgreSQL tests. Only an explicitly supplied disposable ADR database is used."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4
from urllib.parse import urlsplit
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.models import BeleniosBinding, BeleniosOperation, Election, School, User
from app.auth import check_election_access, ROLE_SUPERADMIN
from app.belenios.service import reserve, complete, unknown

URL = os.getenv('ADR001_TEST_PG_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Disposable PostgreSQL URL not supplied')


@pytest.fixture
def pg():
    target = urlsplit(URL)
    allowed = target.hostname == '127.0.0.1' and ((target.port == 55441 and target.path == '/adr001_tests') or
              (os.getenv('REQUIRE_S2_SERVICES') == '1' and target.path.startswith('/s3_') and target.path.endswith('_adr')) or
              (bool(os.getenv('CI')) and target.port == 5432 and target.path == '/theogen_test'))
    assert allowed, 'Only the dedicated local or ephemeral CI test database is allowed'
    engine = create_engine(URL)
    Session = sessionmaker(bind=engine, autoflush=False)
    db = Session()
    school = School(nombre='Synthetic PG ' + uuid4().hex)
    user = User(nombre='Synthetic PG', email=uuid4().hex+'@ejemplo.test', password_hash='not-used', rol=ROLE_SUPERADMIN)
    db.add_all([school,user]); db.flush()
    election=Election(nombre='Synthetic PG',school_id=school.id,estado='Borrador')
    db.add(election); db.flush()
    binding=BeleniosBinding(election_id=election.id,reference=uuid4().hex,policy='R2',phase='Draft',draft_json='{}',approval_ref='pg-test',total_people=2,total_units=2)
    db.add(binding); db.commit()
    yield db, Session, user.id, election.id, binding.id
    db.close(); engine.dispose()


def test_actual_migration_tables_and_legacy_vote_shape(pg):
    db,*_=pg
    inspector=inspect(db.get_bind())
    assert {'belenios_bindings','belenios_units','belenios_operations'}.issubset(inspector.get_table_names())
    assert {'voter_id','candidate_id','hash_integridad'} <= {col['name'] for col in inspector.get_columns('votes')}


def test_two_concurrent_reservations_have_one_winner(pg):
    db,Session,user_id,_,binding_id=pg
    barrier=Barrier(2)
    def worker():
        with Session() as session:
            binding=session.get(BeleniosBinding,binding_id); user=session.get(User,user_id)
            barrier.wait(timeout=10)
            try: reserve(session,binding,user,str(uuid4()),'Open'); return 1
            except HTTPException as error:
                assert error.status_code==409; return 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:worker(),range(2)))
    assert sum(results)==1
    assert db.query(BeleniosOperation).filter_by(binding_id=binding_id).count()==1


def test_late_result_cannot_overwrite_reconciled_state(pg):
    db,_,user_id,_,binding_id=pg
    binding=db.get(BeleniosBinding,binding_id); user=db.get(User,user_id)
    key=reserve(db,binding,user,str(uuid4()),'Open'); complete(db,binding,key,'Open')
    next_key=reserve(db,binding,user,str(uuid4()),'Close'); complete(db,binding,next_key,'Closed')
    for action in (lambda:complete(db,binding,key,'Open'),lambda:unknown(db,binding,key)):
        with pytest.raises(HTTPException): action()
        db.refresh(binding); assert binding.phase=='Closed' and binding.inflight is None


def test_legacy_writer_waits_for_binding_and_then_refuses(pg):
    db,Session,user_id,election_id,binding_id=pg
    # Remove only this synthetic binding, then establish it under the parent-row lock.
    db.delete(db.get(BeleniosBinding,binding_id)); db.commit()
    db.query(Election).filter_by(id=election_id).with_for_update().one()
    binding=BeleniosBinding(election_id=election_id,reference=uuid4().hex,policy='R2',phase='Draft',draft_json='{}',approval_ref='pg-lock-test',total_people=2,total_units=2)
    db.add(binding); db.flush()
    started=Event()
    def writer():
        with Session() as session:
            election=session.get(Election,election_id); user=session.get(User,user_id)
            started.set()
            with pytest.raises(HTTPException) as denied:
                check_election_access(user,election,write=True)
            assert denied.value.status_code==409
    with ThreadPoolExecutor(max_workers=1) as executor:
        future=executor.submit(writer)
        assert started.wait(10)
        db.commit()
        future.result(timeout=10)
