"""Bounded scheduled development, exact-commit CI, and recoverable publication.

The coding process never decides that electoral approvals or independent review passed.
Only this controller stages scoped changes and publishes a candidate after real Azure CI.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'automation' / 'sprint3'
RUNTIME = ROOT / '.runtime' / 'autonomy'
SUBSCRIPTION = '54ce7e6a-e909-4bef-b0cd-8133c2087dcf'
REGISTRY = 'theogenongtcacr'
REPOSITORY = 'OsvaldoVegaOses/_Electoral'
REQUIRED_STAGES = {'synthetic-services', 'backend-migrations-concurrency-restore',
    'frontend-lint', 'frontend-build', 'e2e-real-http-postgresql', 'belenios-ui-api-doubles',
    'python-dependency-audit', 'npm-dependency-audit', 'secrets-current-and-history', 'compose-nginx'}


class NeedsReconciliation(RuntimeError):
    """A remote mutation might have succeeded. Never resubmit it automatically."""


class CiFailed(RuntimeError):
    """Azure positively confirmed a failed run; repair can create a new candidate."""


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def execute(args, cwd=ROOT, timeout=120, data=None):
    executable = shutil.which(str(args[0])) or str(args[0])
    result = subprocess.run([executable, *map(str, args[1:])], cwd=cwd, input=data,
        capture_output=True, timeout=timeout, env={**os.environ, 'PYTHONIOENCODING': 'utf-8',
            'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'})
    if result.returncode:
        # Keep raw diagnostics private; never copy command arguments or secrets into reports.
        raise RuntimeError('Command failed: ' + Path(executable).stem)
    try:
        return result.stdout.decode('utf-8')
    except UnicodeDecodeError:
        return result.stdout.decode('cp1252')


def git(*args, cwd=ROOT):
    return execute(['git', *args], cwd=cwd).strip()


def verify_origin(cwd=ROOT):
    allowed = {'https://github.com/' + REPOSITORY + '.git', 'git@github.com:' + REPOSITORY + '.git'}
    if git('remote', 'get-url', 'origin', cwd=cwd) not in allowed or git('remote', 'get-url', '--push', 'origin', cwd=cwd) not in allowed:
        raise NeedsReconciliation('The remote repository differs from the authorized destination')


def az(*args, timeout=180):
    output = execute(['az', *args, '--subscription', SUBSCRIPTION,
        '--only-show-errors', '-o', 'json'], timeout=timeout)
    return json.loads(output) if output.strip() else None


@contextmanager
def exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a+b')
    handle.seek(0, 2)
    if not handle.tell():
        handle.write(b'0')
        handle.flush()
    handle.seek(0)
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def validate_queue(queue):
    tasks = queue['tasks']
    ids = [task['id'] for task in tasks]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r'S3-A\d{2}', value) for value in ids):
        raise ValueError('Invalid or duplicate task IDs')
    graph = {task['id']: set(task['depends_on']) for task in tasks}
    if any(not dependencies <= set(ids) for dependencies in graph.values()):
        raise ValueError('Unknown dependency')
    visited, visiting = set(), set()
    def visit(identifier):
        if identifier in visiting:
            raise ValueError('Dependency cycle')
        if identifier not in visited:
            visiting.add(identifier)
            for dependency in graph[identifier]:
                visit(dependency)
            visiting.remove(identifier)
            visited.add(identifier)
    for identifier in ids:
        visit(identifier)
    if not 1 <= queue['max_daily_agent_runs'] <= 4 or not 1 <= queue['max_attempts_per_task'] <= 2:
        raise ValueError('Execution budget exceeds the authorized bounds')
    if not 1 <= queue['agent_timeout_minutes'] <= 45 or not 1 <= queue['ci_timeout_minutes'] <= 40:
        raise ValueError('Execution timeout exceeds the authorized bounds')


def choose_task(queue, state, today):
    if sum(run['day'] == today for run in state.get('agent_runs', [])) >= queue['max_daily_agent_runs']:
        return None
    progress = state.get('tasks', {})
    integrated = {key for key, item in progress.items() if item.get('status') == 'integrated'}
    for task in queue['tasks']:
        item = progress.get(task['id'], {})
        if item.get('status') in ('integrated', 'blocked', 'needs_reconciliation'):
            continue
        if item.get('attempts', 0) >= queue['max_attempts_per_task']:
            continue
        if set(task['depends_on']) <= integrated:
            return task
    return None


def validate_changes(paths, patterns, existing_tests=()):
    if not paths or len(paths) != len(set(paths)):
        raise ValueError('No changes or duplicate paths')
    for name in paths:
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name or '..' in path.parts or '\\' in name
                or ':' in name or not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)):
            raise ValueError('Change outside the selected task scope: ' + name)
        if name in existing_tests:
            raise ValueError('Existing tests cannot be weakened or rewritten: ' + name)


def validate_ci_report(report, sha, run_id):
    stages = report.get('stages', [])
    backend = report.get('backend', {})
    if (report.get('source_sha') != sha or report.get('run_id') != run_id or report.get('result') != 'passed'
            or len(stages) != len(REQUIRED_STAGES)
            or {item.get('name') for item in stages} != REQUIRED_STAGES
            or any(item.get('result') != 'passed' for item in stages)
            or backend.get('head') != sha or backend.get('working_tree') is not False
            or backend.get('failures') != 0 or backend.get('skipped') != 0
            or backend.get('test_cases', 0) < 213 or report.get('e2e_tests', 0) < 9
            or report.get('belenios_ui_tests', 0) < 5
            or any(report.get(flag) is not False for flag in ('production_services_modified', 'email_sent', 'pilot_activated'))):
        raise ValueError('Incomplete, mismatched, or unsafe CI evidence')


def terminate_owned_process(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
            capture_output=True, timeout=30, check=True)
    else:
        os.killpg(process.pid, signal.SIGTERM)
    process.wait(timeout=30)


def run_agent(worktree, task, run_directory, queue):
    prompt = (CONFIG / 'instructions.md').read_text(encoding='utf-8')
    prompt += '\n\nTAREA ACTUAL:\n' + json.dumps(task, ensure_ascii=False)
    previous = run_directory.parent.parent / 'tasks' / (task['id'] + '.json')
    if previous.exists():
        prompt += '\n\nESTADO PREVIO DEL CONTROLADOR:\n' + previous.read_text(encoding='utf-8')
    arguments = [shutil.which('codex.cmd') or shutil.which('codex'), 'exec', '--approve-for-me',
        '--sandbox', 'workspace-write', '--cd', str(worktree), '--json', '--color', 'never',
        '--output-schema', str(CONFIG / 'result.schema.json'),
        '--output-last-message', str(run_directory / 'agent-result.json'), '-']
    with (run_directory / 'private-agent.jsonl').open('wb') as log:
        process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=log, stderr=log,
            cwd=worktree, start_new_session=os.name != 'nt')
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.close()
            process.wait(timeout=queue['agent_timeout_minutes'] * 60)
        except BaseException:
            terminate_owned_process(process)
            raise
        if process.returncode:
            raise RuntimeError('The bounded coding process did not finish successfully')
    result = read_json(run_directory / 'agent-result.json')
    if result.get('task_id') != task['id'] or result.get('outcome') not in ('implemented', 'blocked', 'no_change'):
        raise ValueError('Invalid coding result identity')
    return result


def prepare_candidate(task, item, directory, queue):
    worktree = RUNTIME / 'worktrees' / task['id']
    branch = 'auto/sprint3/' + task['id'].lower()
    if not worktree.exists():
        git('worktree', 'add', '-b', branch, str(worktree), 'origin/main')
    if Path(git('rev-parse', '--git-common-dir', cwd=worktree)).is_absolute():
        common = Path(git('rev-parse', '--git-common-dir', cwd=worktree)).resolve()
    else:
        common = (worktree / git('rev-parse', '--git-common-dir', cwd=worktree)).resolve()
    if common != (ROOT / '.git').resolve() or git('branch', '--show-current', cwd=worktree) != branch:
        raise ValueError('Refusing an unrelated checkout')
    base = git('rev-parse', 'HEAD', cwd=worktree)
    expected_head = item.get('candidate_sha') or item.get('base_sha')
    if expected_head and base != expected_head:
        raise NeedsReconciliation('The preserved checkout head changed outside the validated controller flow')
    item.update(worktree=str(worktree), branch=branch, base_sha=base)
    result = run_agent(worktree, task, directory, queue)
    item['agent_result'] = result
    if git('rev-parse', 'HEAD', cwd=worktree) != base:
        raise NeedsReconciliation('The coding process committed without controller validation')
    if result['outcome'] != 'implemented':
        item['status'] = 'blocked'
        return
    rows = [row for row in execute(['git', 'status', '--porcelain=v1', '-z', '-uall'], cwd=worktree).split('\0') if row]
    if any(row[:2] not in (' M', '??', ' D') for row in rows):
        raise ValueError('Unexpected index changes or renames')
    paths = [row[3:] for row in rows]
    existing_tests = set(git('ls-tree', '-r', '--name-only', base, '--', 'backend/tests', 'frontend/e2e', 'frontend/e2e-belenios', cwd=worktree).splitlines())
    validate_changes(paths, task['paths'], existing_tests)
    code = [name for name in paths if not name.startswith(('backend/tests/', 'frontend/e2e', 'doc/'))
            and name.endswith(('.py', '.js', '.jsx', '.mjs'))]
    new_tests = [name for name in paths if name.startswith(('backend/tests/', 'frontend/e2e')) and name not in existing_tests]
    if not code or not new_tests:
        raise ValueError('Implemented requires functional code and new behavior tests, not documentation alone')
    for name in paths:
        path = worktree / name
        if path.is_symlink() or not path.resolve().is_relative_to(worktree.resolve()):
            raise ValueError('Symlink or escaped source path')
    git('diff', '--check', cwd=worktree)
    git('add', '--', *paths, cwd=worktree)
    git('commit', '-m', 'feat(sprint3): ' + task['id'] + ' ' + task['title'], cwd=worktree)
    item.update(candidate_sha=git('rev-parse', 'HEAD', cwd=worktree), status='candidate')


def queue_ci(item, directory):
    worktree = Path(item['worktree'])
    context = directory / 'ci-context'
    execute([sys.executable, worktree / 'scripts/prepare_azure_ci.py', '--output', context], cwd=worktree)
    # Persist the caller's 'submitting_ci' phase BEFORE this potentially ambiguous mutation.
    try:
        response = az('acr', 'run', '--registry', REGISTRY, '--resource-group', 'new',
            '--file', 'acr-task.yaml', '--set', 'expected_sha=' + item['candidate_sha'],
            '--timeout', '3600', '--no-logs', str(context), timeout=180)
    except Exception as error:
        raise NeedsReconciliation('CI submission outcome unknown; inspect Azure without resubmitting') from error
    if not isinstance(response, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]+', response.get('runId', '')):
        raise NeedsReconciliation('CI submission returned no run ID; inspect Azure without resubmitting')
    item.update(ci_run_id=response['runId'], status='ci_running', evidence_directory=str(directory))


def verify_ci(item, queue):
    run_id, sha = item['ci_run_id'], item['candidate_sha']
    deadline = time.monotonic() + queue['ci_timeout_minutes'] * 60
    while True:
        run = az('acr', 'task', 'show-run', '--registry', REGISTRY, '--resource-group', 'new', '--run-id', run_id)
        status = run['status']
        if status == 'Succeeded':
            break
        if status in ('Failed', 'Canceled', 'Error', 'Timeout'):
            raise CiFailed('Azure CI terminal failure: ' + run_id)
        if time.monotonic() >= deadline:
            return False  # Resume this known run next cycle; never submit another run.
        time.sleep(20)
    worktree = Path(item['worktree'])
    relative_log = '.runtime/azure-autonomous-' + run_id + '.log'
    execute(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', worktree / 'scripts/download_azure_ci_logs.ps1',
        '-Registry', REGISTRY, '-ResourceGroup', 'new', '-RunId', run_id, '-Output', relative_log], cwd=worktree)
    output = Path(item['evidence_directory']) / 'ci-report.json'
    execute([sys.executable, worktree / 'scripts/collect_azure_ci.py', '--log-file', worktree / relative_log,
        '--run-id', run_id, '--expected-sha', sha, '--output', output], cwd=worktree)
    report = read_json(output)
    validate_ci_report(report, sha, run_id)
    evidence = az('acr', 'repository', 'show', '--name', REGISTRY, '--image', 'electoral-ci/evidence:' + run_id)
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', evidence.get('digest', '')):
        raise ValueError('Retained CI evidence is missing')
    item.update(status='verified', evidence_digest=evidence['digest'])
    return True


def publish(task, item, directory):
    worktree, branch, sha = Path(item['worktree']), item['branch'], item['candidate_sha']
    verify_origin(worktree)
    base_main = git('merge-base', sha, 'origin/main', cwd=worktree)
    try:
        git('push', '-u', 'origin', branch, cwd=worktree)
    except Exception as error:
        remote = git('ls-remote', 'origin', 'refs/heads/' + branch, cwd=worktree)
        if not remote.startswith(sha + '\t'):
            raise NeedsReconciliation('Branch publication outcome unknown') from error
    prs = json.loads(execute(['gh', 'pr', 'list', '--repo', REPOSITORY, '--head', branch, '--state', 'all',
        '--json', 'number,url,state,headRefOid']))
    if len(prs) > 1 or any(pr['state'] != 'OPEN' or pr['headRefOid'] != sha for pr in prs):
        raise NeedsReconciliation('Unexpected prior pull request; preserve the candidate')
    body = directory / 'pr-body.md'
    body.write_text(f"{task['title']}\n\n{item['agent_result']['summary']}\n\n"
        f"CI Azure `{item['ci_run_id']}` aprobada sobre `{sha}`: diez controles obligatorios, "
        f"backend sin fallos/omisiones, E2E y escaneres. Evidencia OCI: `{item['evidence_digest']}`.\n\n"
        "Desarrollo tecnico sintetico. No acredita revision independiente, G2/G3/G4, entrega real, "
        "custodia externa ni activacion Belenios.\n", encoding='utf-8')
    if prs:
        pr = prs[0]
    else:
        try:
            url = execute(['gh', 'pr', 'create', '--repo', REPOSITORY, '--base', 'main', '--head', branch,
                '--title', task['id'] + ': ' + task['title'], '--body-file', body]).strip()
        except Exception as error:
            raise NeedsReconciliation('PR creation outcome unknown; inspect before retrying') from error
        match = re.fullmatch(r'https://github\.com/OsvaldoVegaOses/_Electoral/pull/(\d+)', url)
        if not match:
            raise NeedsReconciliation('PR identity not confirmed')
        pr = {'number': int(match[1]), 'url': url}
    item.update(pr_number=pr['number'], pr_url=pr['url'])
    status_file = directory / 'azure-status.json'
    write_json(status_file, {'state': 'success', 'context': 'Azure ACR CI / full verification',
        'description': item['ci_run_id'] + ': required stages passed on exact source SHA', 'target_url': pr['url']})
    execute(['gh', 'api', '--method', 'POST', 'repos/' + REPOSITORY + '/statuses/' + sha,
        '--input', status_file])
    git('fetch', 'origin', 'main')
    if git('rev-parse', 'origin/main') != base_main:
        raise NeedsReconciliation('Main advanced during validation; rebase and revalidate before merging')
    try:
        execute(['gh', 'pr', 'merge', str(pr['number']), '--repo', REPOSITORY, '--merge',
            '--match-head-commit', sha], timeout=180)
    except Exception as error:
        raise NeedsReconciliation('Merge outcome unknown; inspect the PR before any further mutation') from error
    confirmation = json.loads(execute(['gh', 'pr', 'view', str(pr['number']), '--repo', REPOSITORY,
        '--json', 'mergedAt,mergeCommit']))
    if not confirmation.get('mergedAt') or not confirmation.get('mergeCommit', {}).get('oid'):
        raise NeedsReconciliation('Merge not confirmed')
    item.update(status='integrated', merge_sha=confirmation['mergeCommit']['oid'], completed_at=timestamp())
    git('fetch', 'origin', 'main')
    if git('branch', '--show-current') == 'main' and not git('status', '--porcelain'):
        try:
            git('merge', '--ff-only', 'origin/main')
        except RuntimeError:
            item['local_checkout_sync_pending'] = True


def preflight():
    for tool in ('git', 'python', 'gh', 'az', 'codex'):
        if not shutil.which(tool):
            raise RuntimeError('Required local tool unavailable: ' + tool)
    execute(['codex', 'login', 'status'])
    verify_origin()
    identity = json.loads(execute(['gh', 'api', 'user']))
    permissions = json.loads(execute(['gh', 'api', 'repos/' + REPOSITORY]))
    if not identity.get('login') or permissions.get('permissions', {}).get('push') is not True:
        raise RuntimeError('The active GitHub identity cannot publish to the authorized repository')
    account = az('account', 'show')
    if account['id'] != SUBSCRIPTION or account['state'] != 'Enabled':
        raise RuntimeError('Authorized Azure subscription is not enabled')
    validate_queue(read_json(CONFIG / 'queue.json'))
    return {'codex_authenticated': True, 'github_authenticated': True, 'azure_subscription': 'Enabled', 'queue_valid': True}


def cycle():
    queue = read_json(CONFIG / 'queue.json')
    validate_queue(queue)
    state_path = RUNTIME / 'state.json'
    state = read_json(state_path) if state_path.exists() else {'tasks': {}, 'agent_runs': []}
    if (RUNTIME / 'paused').exists():
        return {'result': 'paused'}
    if any(item.get('status') == 'needs_reconciliation' for item in state['tasks'].values()):
        return {'result': 'needs_reconciliation', 'details': 'No remote mutation will be repeated'}
    if git('branch', '--show-current') != 'main' or git('status', '--porcelain'):
        return {'result': 'waiting_for_clean_main'}
    preflight()
    git('fetch', 'origin', 'main')
    active = [task for task in queue['tasks'] if state['tasks'].get(task['id'], {}).get('status') in ('ci_running', 'candidate')]
    if len(active) > 1:
        raise ValueError('Multiple active runs require reconciliation')
    task = active[0] if active else choose_task(queue, state, datetime.now().astimezone().date().isoformat())
    if task is None:
        return {'result': 'idle', 'details': 'Budget reached, dependencies pending, or technical queue exhausted; external gates remain separate'}
    item = state['tasks'].setdefault(task['id'], {'attempts': 0})
    directory = Path(item['evidence_directory']) if active else RUNTIME / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + task['id'])
    directory.mkdir(parents=True, exist_ok=True)
    def save():
        state['updated_at'] = timestamp()
        write_json(state_path, state)
        write_json(RUNTIME / 'tasks' / (task['id'] + '.json'), item)
    if not active and item.get('status') in ('coding', 'submitting_ci', 'publishing'):
        item['status'] = 'needs_reconciliation'
        save()
        return {'result': 'needs_reconciliation', 'task': task['id']}
    try:
        if not active:
            item.update(attempts=item['attempts'] + 1, status='coding', started_at=timestamp(), evidence_directory=str(directory))
            state['agent_runs'].append({'day': datetime.now().astimezone().date().isoformat(), 'task': task['id']})
            save()
            prepare_candidate(task, item, directory, queue)
            save()
            if item['status'] == 'blocked':
                return {'result': 'blocked', 'task': task['id']}
        if item['status'] == 'candidate':
            item['status'] = 'submitting_ci'
            save()
            queue_ci(item, directory)
            save()
        if not verify_ci(item, queue):
            save()
            return {'result': 'ci_running', 'task': task['id'], 'run_id': item['ci_run_id']}
        item['status'] = 'publishing'
        save()
        publish(task, item, directory)
        save()
        return {'result': 'integrated', 'task': task['id'], 'pr': item['pr_url'], 'electoral_acceptance': 'pending_external'}
    except NeedsReconciliation as error:
        item.update(status='needs_reconciliation', error=str(error))
        save()
        return {'result': 'needs_reconciliation', 'task': task['id'], 'details': str(error)}
    except Exception as error:
        if item.get('status') == 'publishing':
            item.update(status='needs_reconciliation', error='Publication interrupted; inspect remote branch and PR before any retry')
            save()
            return {'result': 'needs_reconciliation', 'task': task['id']}
        if item.get('status') == 'ci_running' and not isinstance(error, CiFailed):
            # Retry only collection of a KNOWN run, never re-code/resubmit for a read failure.
            item['evidence_collection_error'] = type(error).__name__
            if isinstance(error, ValueError):
                item['status'] = 'needs_reconciliation'
            save()
            return {'result': item['status'], 'task': task['id'], 'run_id': item['ci_run_id']}
        item.update(status='failed', error=type(error).__name__ + ': ' + str(error), failed_at=timestamp())
        if item['attempts'] >= queue['max_attempts_per_task']:
            item['status'] = 'blocked'
        save()
        return {'result': item['status'], 'task': task['id'], 'details': item['error']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'status', 'preflight', 'pause', 'resume'))
    arguments = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if arguments.action == 'status':
        print(json.dumps(read_json(RUNTIME / 'state.json') if (RUNTIME / 'state.json').exists() else {'result': 'not_started'}, ensure_ascii=False))
        return
    if arguments.action in ('pause', 'resume'):
        path = RUNTIME / 'paused'
        if arguments.action == 'pause':
            path.touch()
        elif path.exists():
            path.unlink()
        print(json.dumps({'result': arguments.action, 'effective': 'before next cycle'}))
        return
    try:
        with exclusive_lock(RUNTIME / 'controller.lock'):
            result = preflight() if arguments.action == 'preflight' else cycle()
            write_json(RUNTIME / 'latest.json', {'recorded_at': timestamp(), **result})
            print(json.dumps(result, ensure_ascii=False))
    except (BlockingIOError, PermissionError):
        print(json.dumps({'result': 'locked_or_access_denied', 'details': 'Inspect persisted phase before retrying'}))
        raise SystemExit(2)
    except Exception as error:
        result = {'recorded_at': timestamp(), 'result': 'preflight_or_controller_failed',
                  'details': type(error).__name__ + ': ' + str(error)}
        write_json(RUNTIME / 'latest.json', result)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
