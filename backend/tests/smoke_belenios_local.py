"""Explicit mutating laboratory protocol; not collected by pytest. No real identities."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import SecretStr
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app
from app.config import settings
from app.database import Base, get_db
from app.auth import get_current_user, ROLE_SUPERADMIN
from app.models import BeleniosBinding, Election, School, User, Candidate, Voter

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / '.runtime/adr-live'
PRIVATE.mkdir(parents=True, exist_ok=True)
STATE = PRIVATE / 'state.json'
spec = importlib.util.spec_from_file_location('lab_tools', ROOT / 'poc/belenios-3.3.0/tests/setup_h2.py')
lab = importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)
lab.PRIVATE = PRIVATE
lab.STATE_PATH = PRIVATE / 'provider-journal.json'
lab.TRACE_PATH = PRIVATE / 'provider-trace.json'
if lab.STATE_PATH.exists(): lab.STATE = json.loads(lab.STATE_PATH.read_text())
if lab.TRACE_PATH.exists(): lab.TRACE = json.loads(lab.TRACE_PATH.read_text())
settings.BELENIOS_MODE, settings.ENVIRONMENT = 'laboratory', 'development'
api = lab.API(18002)
api.token = api.call('POST', 'login/demo', {'username': 'poc-admin'})['token']
settings.BELENIOS_R2_ADMIN_TOKEN = SecretStr(api.token)
settings.BELENIOS_VERIFIER_IMAGE = json.loads((ROOT / 'doc/poc-belenios/evidencias/h1-resultados.json').read_text())['image_id']
lab.IMAGE = settings.BELENIOS_VERIFIER_IMAGE
engine = create_engine('sqlite:///' + (PRIVATE / 'application.sqlite').as_posix(), connect_args={'check_same_thread': False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autoflush=False)
db = Session()
app.dependency_overrides[get_db] = lambda: db
client = TestClient(app)


def action(election_id, operation):
    result = client.post(f'/api/elections/{election_id}/belenios/transition', json={'request_id': str(uuid4()), 'action': operation})
    if result.status_code != 200:
        raise RuntimeError('Transition ' + operation + ' failed: ' + result.text)


def authorities(uuid, voters):
    base = 'elections/' + uuid
    directory = PRIVATE / 'authority'
    directory.mkdir(exist_ok=True)
    (directory / 'voters.txt').write_text('\n'.join(voters) + '\n')
    if not list(directory.glob('*.privcreds')):
        lab.tool(directory, 'setup', 'generate-credentials', '--uuid', uuid, '--group', 'Ed25519', '--file', 'voters.txt')
    assert len(list(directory.glob('*.privcreds'))) == len(list(directory.glob('*.pubcreds'))) == 1
    assert set(json.loads(next(directory.glob('*.privcreds')).read_text())) == set(voters)
    raw_cap = api.call('GET', base + '/draft/credentials/token', raw=True).decode()
    try: cap = json.loads(raw_cap)
    except ValueError: cap = raw_cap
    api.call('POST', base + '/draft/credentials/public', json.loads(next(directory.glob('*.pubcreds')).read_text()), token=cap)
    api.call('POST', base + '/draft/trustees', ['SetThreshold', 0], match=True)
    for i in (1, 2, 3):
        api.call('POST', base + '/draft/trustees', ['Add', {'address': f'trustee{i}@ejemplo.test', 'name': f'Trustee {i}'}], match=True)
    api.call('POST', base + '/draft/trustees', ['SetThreshold', 2], match=True)
    trustees = api.call('GET', base + '/draft/trustees')[1]['trustees']
    custodians = []
    for i, trustee in enumerate(trustees, 1):
        custody = PRIVATE / f'trustee-{i}'
        key = lab.tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--threshold-context', f'{i}/2/3', '--step', '1').decode().strip()
        custodians.append({'directory': str(custody), 'key_id': key, 'index': i})
        api.call('POST', base + '/draft/trustee', (custody / (key + '.cert')).read_bytes(), token=trustee['token'])
    for index, trustee in enumerate(trustees):
        status = api.call('GET', base + '/draft/trustee', token=trustee['token'])[1][1]
        custody, key = Path(custodians[index]['directory']), custodians[index]['key_id']
        (custody / 'certs.jsons').write_text(''.join(json.dumps(cert, separators=(',', ':')) + '\n' for cert in status['certs']))
        output = lab.tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--certs', 'certs.jsons', '--key', key + '.key', '--step', '3')
        api.call('POST', base + '/draft/trustee', output, token=trustee['token'])
    for index, trustee in enumerate(trustees):
        status = api.call('GET', base + '/draft/trustee', token=trustee['token'])[1][1]
        custody, key = Path(custodians[index]['directory']), custodians[index]['key_id']
        output = lab.tool(custody, 'setup', 'generate-trustee-key-threshold', '--group', 'Ed25519', '--certs', 'certs.jsons', '--key', key + '.key', '--step', '5', stdin=json.dumps(status['vinput']).encode() + b'\n')
        (custody / (key + '.dkey')).write_text(json.loads(output)['private_key'] + '\n')
        api.call('POST', base + '/draft/trustee', output, token=trustee['token'])
    return str(next(directory.glob('*.privcreds'))), custodians


def main(phase):
    if phase == 'prepare':
        if STATE.exists():
            raise SystemExit('Existing live intent/state: reconcile, do not create again')
        STATE.write_text(json.dumps({'phase': 'prepare_intent'}))
        school = School(nombre='Institucion sintetica ADR'); db.add(school); db.flush()
        user = User(nombre='Operador sintetico', email='operador@ejemplo.test', password_hash='not-used', rol=ROLE_SUPERADMIN)
        election = Election(nombre='Integracion ADR ficticia', school_id=school.id, estado='Borrador', regla_votacion='Un voto por familia')
        db.add_all([user, election]); db.flush()
        voters = [Voter(election_id=election.id, nombre=f'Persona ficticia {i}', rut=f'SYNTHETIC-{i}', rut_normalizado=f'SYNTHETIC-{i}', familia_id='ficticia-1' if i < 2 else 'ficticia-2', correo=f'apoderado{i}@ejemplo.test') for i in range(3)]
        db.add_all(voters); db.add_all([Candidate(election_id=election.id, nombre=label, es_blanco=False, es_nulo=False) for label in ('Lista A', 'Lista B')]); db.commit()
        app.dependency_overrides[get_current_user] = lambda: user
        response = client.post(f'/api/elections/{election.id}/belenios/prepare', json={'request_id': str(uuid4()), 'policy': 'R2', 'representative_ids': [voters[0].id, voters[2].id],
                                  'approval_ref': 'poc-adr-live', 'ballot_mode': 'mandatory_single_choice_no_blank_no_null', 'synthetic_laboratory': True})
        binding = db.query(BeleniosBinding).filter_by(election_id=election.id).one()
        state = {'phase': 'prepared' if response.status_code == 201 else 'reconciliation_required', 'election_id': election.id, 'user_id': user.id, 'uuid': binding.remote_uuid}
        STATE.write_text(json.dumps(state))
        assert response.status_code == 201, response.text
        print(json.dumps({'live_prepare': 'PASS', 'uuid': binding.remote_uuid, 'people': 3, 'family_units': 2}))
        return
    state = json.loads(STATE.read_text())
    user = db.get(User, state['user_id']); app.dependency_overrides[get_current_user] = lambda: user
    election_id, uuid = state['election_id'], state['uuid']
    binding = db.query(BeleniosBinding).filter_by(election_id=election_id).one()
    if phase == 'export-public':
        assert state['phase'] == 'complete'
        from app.belenios.verification import public_archive
        import hashlib
        data = public_archive('R2', uuid)
        result = client.get(f'/api/elections/{election_id}/belenios/record').json()
        assert hashlib.sha256(data).hexdigest() == result['archive_sha256']
        assert b'@ejemplo.test' not in data
        assert not any(value.encode() in data for value in json.loads(Path(state['private_credentials_file']).read_text()).values())
        target = ROOT/'doc/motor/evidencias'
        (target/(uuid+'.bel')).write_bytes(data)
        report_path = target/'adr001-live.json'
        report = json.loads(report_path.read_text())
        report['public_archive_repository_path'] = 'doc/motor/evidencias/'+uuid+'.bel'
        report_path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'public_archive_export':'PASS','sha256':result['archive_sha256']}))
    elif phase == 'resume-open':
        assert state['phase'] == 'authority_intent' and binding.phase == 'Draft' and not binding.inflight
        status=api.call('GET','elections/'+uuid+'/draft/status')
        assert status['credentials_ready'] and status['trustees_ready']
        aliases=[row['alias'] for row in client.get(f'/api/elections/{election_id}/belenios/units').json()['units']]
        custodians=[]
        for i in (1,2,3):
            custody=PRIVATE/f'trustee-{i}'; keys=list(custody.glob('*.key')); assert len(keys)==1
            assert (custody/(keys[0].stem+'.dkey')).exists()
            custodians.append({'directory':str(custody),'key_id':keys[0].stem,'index':i})
        state.update(phase='authorities_ready',voters=aliases,private_credentials_file=str(next((PRIVATE/'authority').glob('*.privcreds'))),trustees=custodians)
        STATE.write_text(json.dumps(state))
        action(election_id,'ValidateElection'); action(election_id,'Open')
        state['phase']='open'; STATE.write_text(json.dumps(state))
        print(json.dumps({'live_authorities_and_open':'PASS','external_threshold':'2/3'}))
    elif phase in ('authorities', 'resume-authority-read'):
        if phase == 'resume-authority-read':
            status = api.call('GET', 'elections/' + uuid + '/draft/status')
            trustees = api.call('GET', 'elections/' + uuid + '/draft/trustees')
            assert state['phase'] == 'authority_intent' and not status['credentials_ready'] and trustees == ['Basic', {'trustees': []}]
            assert list((PRIVATE / 'authority').glob('*.privcreds'))
        elif state['phase'] != 'prepared': raise SystemExit('Existing ceremony state: reconcile')
        state['phase'] = 'authority_intent'; STATE.write_text(json.dumps(state))
        aliases = [row['alias'] for row in client.get(f'/api/elections/{election_id}/belenios/units').json()['units']]
        credentials, trustees = authorities(uuid, aliases)
        state.update(phase='authorities_ready',voters=aliases,private_credentials_file=credentials,trustees=trustees)
        STATE.write_text(json.dumps(state))
        action(election_id, 'ValidateElection'); action(election_id, 'Open')
        state.update(phase='open', voters=aliases, private_credentials_file=credentials, trustees=trustees)
        STATE.write_text(json.dumps(state))
        print(json.dumps({'live_authorities_and_open': 'PASS', 'external_threshold': '2/3'}))
    elif phase == 'tally':
        if state['phase'] != 'votes_confirmed': raise SystemExit('Two confirmed native votes required')
        state['phase'] = 'tally_intent'; STATE.write_text(json.dumps(state))
        action(election_id, 'Close'); action(election_id, 'ComputeEncryptedTally')
        base = 'elections/' + uuid
        import subprocess, hashlib
        archive = subprocess.run(['docker','run','--rm','--network','theogen-belenios33-poc_ballot-b','--entrypoint',lab.TOOL,lab.IMAGE,'archive','pull','--url','http://single:8001/','--uuid',uuid],capture_output=True,check=True).stdout
        partials = api.call('GET', base + '/partial-decryptions')
        for trustee in state['trustees'][:2]:
            custody, key, i = Path(trustee['directory']), trustee['key_id'], trustee['index']
            (custody / (uuid + '.bel')).write_bytes(archive)
            output = lab.tool(custody,'election','decrypt-threshold','--key',key+'.key','--decryption-key',key+'.dkey','--trustee-id',str(i+1))
            cap = next(t['token'] for t in partials['trustees'] if t['address'] == f'trustee{i}@ejemplo.test')
            api.call('POST', base + '/trustee', output.splitlines()[0], token=cap)
        action(election_id, 'ReleaseTally')
        final = subprocess.run(['docker','run','--rm','--network','theogen-belenios33-poc_ballot-b','--entrypoint',lab.TOOL,lab.IMAGE,'archive','pull','--url','http://single:8001/','--uuid',uuid],capture_output=True,check=True).stdout
        anchor = {'final_event_hash':api.call('GET',base+'/last-event')['hash'],'result_object_hash':api.call('GET',base+'/roots')['result'],'archive_sha256':hashlib.sha256(final).hexdigest(),'anchor_reference':'poc-review-same-host'}
        response = client.post(f'/api/elections/{election_id}/belenios/verify',json=anchor)
        assert response.status_code == 200, response.text
        evidence=response.json(); assert [row['votes'] for row in evidence['options']] == [1,1]
        assert client.get(f'/api/elections/{election_id}/belenios/record').json()==evidence
        target=ROOT/'doc/motor/evidencias'; target.mkdir(parents=True,exist_ok=True)
        (target/'adr001-live.json').write_text(json.dumps({'tested_at_utc':datetime.now(timezone.utc).isoformat(),'result':evidence,'operations':[op.kind for op in db.query(__import__('app.models',fromlist=['BeleniosOperation']).BeleniosOperation).all()], 'limits':['Same host/operator; simulated independence','SQLite application DB for this live protocol; PostgreSQL tested separately','Original Belenios UI; no private keys/ballots sent to TheoGen']},indent=2)+'\n')
        state['phase']='complete'; STATE.write_text(json.dumps(state))
        print(json.dumps({'live_management_to_verified_record':'PASS','result':[1,1],'private_keys_received_by_theogen':False}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('phase',choices=['prepare','authorities','resume-authority-read','resume-open','tally','export-public']); args=parser.parse_args()
    main(args.phase)
