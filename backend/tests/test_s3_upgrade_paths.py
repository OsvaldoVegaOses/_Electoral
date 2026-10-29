"""Upgrade already-applied S2-B/ADR schemas; only the runner's disposable DB is reset."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

URL=os.getenv('S3_UPGRADE_DATABASE_URL','')
if not URL:
    if os.getenv('REQUIRE_S2_SERVICES')=='1':raise RuntimeError('S3_UPGRADE_DATABASE_URL is required')
    pytest.skip('Disposable PostgreSQL upgrade database is not configured',allow_module_level=True)
if not URL.startswith('postgresql') or not (make_url(URL).database or '').startswith('s3_') or os.getenv('ENVIRONMENT')!='test':
    raise RuntimeError('Upgrade tests require an explicitly disposable s3_ PostgreSQL database in test')
BACKEND=Path(__file__).resolve().parents[1]


def alembic(action,target,success=True):
    result=subprocess.run([sys.executable,'-m','alembic',action,target],cwd=BACKEND,
        env={**os.environ,'DATABASE_URL':URL},capture_output=True,text=True,encoding='utf-8',timeout=45)
    assert (result.returncode==0)==success,result.stderr
    return result


def rows(connection,table,columns='*'):
    return connection.execute(text(f'SELECT {columns} FROM {table} ORDER BY id')).all()


@pytest.mark.parametrize('start',['f6a7b8c9d0e1','bel001_20261028'])
def test_applied_schema_upgrades_preserve_votes_snapshots_and_remote_intents(start):
    engine=create_engine(URL)
    try:
        with engine.begin() as db:
            db.execute(text('DROP SCHEMA public CASCADE'))
            db.execute(text('CREATE SCHEMA public'))
        alembic('upgrade',start)
        snapshot=json.dumps({'election_id':4,'total_padron':5,'total_habilitados':2,'legacy':'frozen'},sort_keys=True)
        binding_id=None
        with engine.begin() as db:
            db.execute(text("INSERT INTO schools(id,nombre) VALUES(1,'Synthetic Upgrade')"))
            db.execute(text("INSERT INTO users(id,nombre,email,password_hash,rol) VALUES(1,'Synthetic','upgrade@example.org','unused','Administrador General')"))
            for identity,state,rule,people,units in [
                (1,'Borrador','Un voto por familia',None,None),
                (2,'Abierta','Un voto por familia',5,2),
                (3,'Cerrada','Un voto por persona',2,2),
                (4,'Finalizada','Un voto por familia',5,2),
                (5,'Finalizada','Un voto por familia',5,None),
                (6,'Finalizada','Un voto por familia',0,0),
                (8,'Borrador','Un voto por persona',None,None),
            ]:
                db.execute(text('INSERT INTO elections(id,nombre,school_id,estado,regla_votacion,total_padron_congelado,total_habilitados_congelado,tipo_votacion) '
                    "VALUES(:id,:name,1,:state,:rule,:people,:units,'Synthetic')"),
                    {'id':identity,'name':'Synthetic '+str(identity),'state':state,'rule':rule,'people':people,'units':units})
            for election,count in [(2,5),(3,2),(4,5),(5,5),(8,1)]:
                for number in range(count):
                    db.execute(text('INSERT INTO voters(nombre,rut,rut_normalizado,familia_id,election_id,estado) '
                        "VALUES('Synthetic',:rut,:rut,:family,:election,'Pendiente')"),
                        {'rut':f'SYNTH-{election}-{number}','family':'FAMILY-A' if number<3 else 'FAMILY-B','election':election})
            for election in (2,3,4):
                voter_id=db.execute(text('SELECT min(id) FROM voters WHERE election_id=:id'),{'id':election}).scalar_one()
                candidate=db.execute(text("INSERT INTO candidates(nombre,election_id) VALUES('Synthetic',:id) RETURNING id"),{'id':election}).scalar_one()
                db.execute(text('INSERT INTO votes(candidate_id,voter_id,election_id,hash_integridad) VALUES(:candidate,:voter,:id,:hash)'),
                    {'candidate':candidate,'voter':voter_id,'id':election,'hash':'recognized-'+str(election)})
                keys=['RUT:123456785','RUT:162345672'] if election==3 else ['FAM:FAMILY-A','FAM:FAMILY-B']
                for index,key in enumerate(keys):
                    db.execute(text('INSERT INTO voting_entitlements(election_id,unit_key,estado,voter_id_consumidor) VALUES(:id,:key,:state,:voter)'),
                        {'id':election,'key':key,'state':'Consumido' if index==0 else 'Pendiente','voter':voter_id if index==0 else None})
                db.execute(text("UPDATE voters SET estado='Votó' WHERE id=:id"),{'id':voter_id})
            db.execute(text('UPDATE elections SET config_snapshot=:snapshot,config_hash=:hash,fecha_cierre_efectiva=:closed WHERE id=4'),
                {'snapshot':snapshot,'hash':hashlib.sha256(snapshot.encode()).hexdigest(),'closed':'2026-10-20T10:00:00Z'})
            if start=='bel001_20261028':
                key=str(uuid4())
                binding_id=db.execute(text("INSERT INTO belenios_bindings(election_id,reference,policy,remote_uuid,phase,inflight,draft_json,approval_ref,total_people,total_units,created_at) "
                    "VALUES(8,:ref,'R2','Abc123Def456Gh','UNKNOWN',:key,'{}','synthetic',1,1,CURRENT_TIMESTAMP) RETURNING id"),
                    {'ref':uuid4().hex,'key':key}).scalar_one()
                representative=db.execute(text('SELECT id FROM voters WHERE election_id=8')).scalar_one()
                db.execute(text("INSERT INTO belenios_units(binding_id,representative_id,alias) VALUES(:binding,:voter,'synthetic@ejemplo.test')"),
                    {'binding':binding_id,'voter':representative})
                db.execute(text("INSERT INTO belenios_operations(id,binding_id,operator_id,kind,phase,created_at) VALUES(:key,:binding,1,'Prepare','UNKNOWN',CURRENT_TIMESTAMP)"),
                    {'key':key,'binding':binding_id})
            before={table:rows(db,table) for table in ('votes','voters','candidates','schools','users','audit_logs')}
            rights=rows(db,'voting_entitlements','id,election_id,estado,voter_id_consumidor')
            frozen=db.execute(text('SELECT config_snapshot,config_hash,fecha_cierre_efectiva FROM elections WHERE id=4')).one()
            remote={table:rows(db,table) for table in ('belenios_bindings','belenios_units','belenios_operations')} if binding_id else {}
        alembic('upgrade','head')
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()==['s3002_delivery']
            assert before=={table:rows(db,table) for table in before}
            assert rights==rows(db,'voting_entitlements','id,election_id,estado,voter_id_consumidor')
            assert all(key.startswith('h1:') for key in db.execute(text('SELECT unit_key FROM voting_entitlements')).scalars())
            assert frozen==db.execute(text('SELECT config_snapshot,config_hash,fecha_cierre_efectiva FROM elections WHERE id=4')).one()
            assert db.execute(text('SELECT total_habilitados_congelado FROM elections WHERE id=5')).scalar_one()==2
            assert db.execute(text('SELECT total_padron_congelado,total_habilitados_congelado FROM elections WHERE id=6')).one()==(None,None)
            assert db.execute(text('SELECT total_padron_congelado,total_habilitados_congelado FROM elections WHERE id=2')).one()==(5,2)
            assert remote=={table:rows(db,table) for table in remote}
            assert db.execute(text('SELECT motor FROM elections WHERE id=8')).scalar_one()==('belenios' if binding_id else 'mvp')
            assert db.execute(text('SELECT count(*) FROM votes WHERE election_id=2')).scalar_one()/2==0.5
        # A failed downgrade must roll back its DDL as well as preserve recognized votes.
        result=alembic('downgrade','base',success=False)
        assert 'respaldo' in result.stderr.lower()
        with engine.connect() as db:
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalars().all()==['s3002_delivery']
            assert before=={table:rows(db,table) for table in before}
            assert remote=={table:rows(db,table) for table in remote}
    finally:
        engine.dispose()
