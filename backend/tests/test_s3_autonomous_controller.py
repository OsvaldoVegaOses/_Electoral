"""The autonomous writer cannot replace proof, broaden scope, or approve an election."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import pytest

SOURCE=Path(__file__).resolve().parents[2]/'automation/sprint3/controller.py'
spec=importlib.util.spec_from_file_location('sprint3_controller',SOURCE)
controller=importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


def queue():
    return {'max_daily_agent_runs':4,'max_attempts_per_task':2,'agent_timeout_minutes':45,
      'ci_timeout_minutes':40,'tasks':[
        {'id':'S3-A01','depends_on':[]},
        {'id':'S3-A02','depends_on':['S3-A01']},
        {'id':'S3-A03','depends_on':[]}]}


def evidence():
    return {'source_sha':'a'*40,'run_id':'test-run','result':'passed',
      'stages':[{'name':name,'result':'passed'} for name in controller.REQUIRED_STAGES],
      'backend':{'head':'a'*40,'working_tree':False,'failures':0,'skipped':0,'test_cases':213},
      'e2e_tests':9,'belenios_ui_tests':5,'production_services_modified':False,
      'email_sent':False,'pilot_activated':False}


def test_completed_code_does_not_satisfy_dependency_until_integrated():
    state={'tasks':{'S3-A01':{'status':'blocked','attempts':2}},'agent_runs':[]}
    assert controller.choose_task(queue(),state,'2026-10-30')['id']=='S3-A03'
    state['tasks']['S3-A01']['status']='integrated'
    assert controller.choose_task(queue(),state,'2026-10-30')['id']=='S3-A02'


def test_daily_budget_blocks_new_agent_but_resets_next_day():
    state={'agent_runs':[{'day':'2026-10-30'} for _ in range(4)]}
    assert controller.choose_task(queue(),state,'2026-10-30') is None
    assert controller.choose_task(queue(),state,'2026-10-31')['id']=='S3-A01'


@pytest.mark.parametrize('change',['duplicate','unknown','cycle','unbounded'])
def test_invalid_work_graph_and_budget_fail_before_execution(change):
    value=queue()
    if change=='duplicate':value['tasks'][1]['id']='S3-A01'
    elif change=='unknown':value['tasks'][1]['depends_on']=['S3-A99']
    elif change=='cycle':value['tasks'][0]['depends_on']=['S3-A02']
    else:value['max_daily_agent_runs']=5
    with pytest.raises(ValueError):controller.validate_queue(value)


@pytest.mark.parametrize('path',[
    'ci/azure/run.py','.gitleaks.toml','automation/sprint3/queue.json',
    'backend/app/belenios/../../credentials.py','backend\\app\\belenios\\x.py',
    '/backend/app/belenios/x.py','backend/app/belenios//x.py',
    'backend/app/belenios/C:secret.py'])
def test_writer_cannot_escape_scope_or_replace_trusted_controls(path):
    with pytest.raises(ValueError):
        controller.validate_changes([path],['backend/app/belenios/*.py'])


def test_existing_tests_cannot_be_rewritten_even_inside_an_allowed_pattern():
    path='backend/tests/test_s3_new_contract.py'
    with pytest.raises(ValueError):
        controller.validate_changes([path],['backend/tests/test_s3_*.py'],[path])
    controller.validate_changes([path],['backend/tests/test_s3_*.py'],[])


@pytest.mark.parametrize('change',['sha','backend_sha','omission','duplicate','skip','dirty','fake_pass','activation','no_safety_flag'])
def test_ci_requires_exact_source_and_all_safe_gates(change):
    report=evidence()
    if change=='sha':report['source_sha']='b'*40
    elif change=='backend_sha':report['backend']['head']='b'*40
    elif change=='omission':report['stages'].pop()
    elif change=='duplicate':report['stages'].append(copy.copy(report['stages'][0]))
    elif change=='skip':report['backend']['skipped']=1
    elif change=='dirty':report['backend']['working_tree']=True
    elif change=='fake_pass':report['stages'][0]['result']='failed'
    elif change=='activation':report['pilot_activated']=True
    else:report.pop('email_sent')
    with pytest.raises(ValueError):controller.validate_ci_report(report,'a'*40,'test-run')


def test_verified_technical_ci_retains_pending_external_custody():
    report=evidence()
    report['backend']['independent_custody']=False
    controller.validate_ci_report(report,'a'*40,'test-run')
    assert report['backend']['independent_custody'] is False


def test_lock_prevents_a_second_process_and_releases_after_exit(tmp_path):
    path=tmp_path/'exclusive.lock'
    code=('import importlib.util,sys; '
      's=importlib.util.spec_from_file_location("controller",sys.argv[1]); '
      'm=importlib.util.module_from_spec(s);s.loader.exec_module(m); '
      'lock=m.exclusive_lock(sys.argv[2]);lock.__enter__();lock.__exit__(None,None,None)')
    with controller.exclusive_lock(path):
        result=subprocess.run([sys.executable,'-c',code,str(SOURCE),str(path)],capture_output=True)
        assert result.returncode!=0
    result=subprocess.run([sys.executable,'-c',code,str(SOURCE),str(path)],capture_output=True)
    assert result.returncode==0


@pytest.mark.parametrize('tag',['failure','error','skipped'])
def test_browser_junit_refuses_failures_and_omissions(tmp_path,tag):
    specification=importlib.util.spec_from_file_location('azure_ci_run',SOURCE.parents[2]/'ci/azure/run.py')
    module=importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    path=tmp_path/'browser.xml'
    path.write_text(f'<testsuite><testcase><{tag}/></testcase></testsuite>')
    with pytest.raises(RuntimeError):module.junit_cases(path,1)


def test_browser_junit_counts_added_tests_and_rejects_missing_baseline(tmp_path):
    specification=importlib.util.spec_from_file_location('azure_ci_run',SOURCE.parents[2]/'ci/azure/run.py')
    module=importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    path=tmp_path/'browser.xml'
    path.write_text('<testsuite>'+6*'<testcase/>'+'</testsuite>')
    assert len(module.junit_cases(path,5))==6
    with pytest.raises(RuntimeError):module.junit_cases(path,9)


def isolated_controller(monkeypatch,tmp_path,status):
    config=tmp_path/'config';config.mkdir()
    runtime=tmp_path/'runtime';runtime.mkdir()
    monkeypatch.setattr(controller,'CONFIG',config)
    monkeypatch.setattr(controller,'RUNTIME',runtime)
    controller.write_json(config/'queue.json',queue())
    controller.write_json(runtime/'state.json',{'agent_runs':[],'tasks':{'S3-A01':{
      'status':status,'attempts':1,'ci_run_id':'known-run','candidate_sha':'a'*40,
      'evidence_directory':str(runtime/'evidence')}}})
    monkeypatch.setattr(controller,'preflight',lambda:None)
    monkeypatch.setattr(controller,'git',lambda *args,**kwargs:'main' if args==('branch','--show-current') else '')
    def unexpected(*args,**kwargs):pytest.fail('A known or ambiguous action must not start another coding/submission cycle')
    monkeypatch.setattr(controller,'prepare_candidate',unexpected)
    monkeypatch.setattr(controller,'queue_ci',unexpected)
    monkeypatch.setattr(controller,'publish',unexpected)
    return runtime


def test_ci_read_failure_resumes_known_run_without_another_submission(monkeypatch,tmp_path):
    runtime=isolated_controller(monkeypatch,tmp_path,'ci_running')
    def unavailable(*args):raise RuntimeError('Read unavailable')
    monkeypatch.setattr(controller,'verify_ci',unavailable)
    result=controller.cycle()
    assert result['result']=='ci_running'
    assert result['run_id']=='known-run'
    assert controller.read_json(runtime/'state.json')['tasks']['S3-A01']['attempts']==1


@pytest.mark.parametrize('phase',['coding','submitting_ci','publishing'])
def test_interrupted_mutation_blocks_repetition_and_preserves_candidate(monkeypatch,tmp_path,phase):
    runtime=isolated_controller(monkeypatch,tmp_path,phase)
    assert controller.cycle()['result']=='needs_reconciliation'
    saved=controller.read_json(runtime/'state.json')['tasks']['S3-A01']
    assert saved['candidate_sha']=='a'*40
    assert saved['attempts']==1
    assert controller.cycle()['result']=='needs_reconciliation'


@pytest.mark.parametrize('change',['extra','sha','digest','private'])
def test_cloud_source_rejects_private_or_mismatched_context_before_network(tmp_path,change):
    specification=importlib.util.spec_from_file_location('azure_submit',SOURCE.parent/'azure_ci_submit.py')
    module=importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    import hashlib,json
    for name in ('Dockerfile','acr-task.yaml','source.bundle'):(tmp_path/name).write_bytes(b'public fixture')
    manifest={'source_sha':'a'*40,'private_runtime_included':False,
      'bundle_sha256':hashlib.sha256((tmp_path/'source.bundle').read_bytes()).hexdigest()}
    if change=='extra':(tmp_path/'.env').write_text('synthetic-only')
    elif change=='sha':manifest['source_sha']='b'*40
    elif change=='digest':manifest['bundle_sha256']='b'*64
    else:manifest['private_runtime_included']=True
    (tmp_path/'source-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):module.public_archive(tmp_path,'a'*40)


def test_cloud_source_contains_only_public_context_files(tmp_path):
    specification=importlib.util.spec_from_file_location('azure_submit',SOURCE.parent/'azure_ci_submit.py')
    module=importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    import hashlib,json,io,tarfile
    for name in ('Dockerfile','acr-task.yaml','source.bundle'):(tmp_path/name).write_bytes(b'public fixture')
    (tmp_path/'source-manifest.json').write_text(json.dumps({'source_sha':'a'*40,'private_runtime_included':False,
      'bundle_sha256':hashlib.sha256((tmp_path/'source.bundle').read_bytes()).hexdigest()}))
    payload=module.public_archive(tmp_path,'a'*40)
    with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
        assert set(archive.getnames())==module.FILES
        assert archive.extractfile('source.bundle').read()==b'public fixture'
