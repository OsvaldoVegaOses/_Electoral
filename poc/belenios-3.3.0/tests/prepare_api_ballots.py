"""Generate extra valid synthetic ballots with the official offline CLI."""
import json
from pathlib import Path
import shutil
import subprocess
import setup_h2 as lab

lab.STATE = json.loads(lab.STATE_PATH.read_text())
lab.TRACE = json.loads(lab.TRACE_PATH.read_text())
for mode, election in lab.STATE['elections'].items():
    mode_dir = lab.ROOT / '.runtime/public' / mode / 'before-tally'
    mode_dir.mkdir(parents=True, exist_ok=True)
    command = ['docker', 'run', '--rm', '--network', 'theogen-belenios33-poc_ballot-' + ('a' if mode == 'revote' else 'b'),
               '--entrypoint', lab.TOOL, lab.IMAGE, 'archive', 'pull', '--url', f'http://{mode}:8001/', '--uuid', election['uuid']]
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        raise SystemExit('Public archive collection failed; no mutation retried')
    archive = mode_dir / (election['uuid'] + '.bel')
    archive.write_bytes(result.stdout)
    directory = lab.PRIVATE / election['uuid'] / 'api-ballot'
    directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(archive, directory / archive.name)
    creds = json.loads(Path(election['private_credentials_file']).read_text())
    (directory / 'credential.txt').write_text(creds[election['voters'][0]] + '\n', encoding='ascii')
    (directory / 'choice.json').write_text('[[0,1]]\n', encoding='ascii')
    ballot_path = directory / 'ballot.json'
    if not ballot_path.exists():
        ballot = lab.tool(directory, 'election', 'generate-ballot', '--privcred', 'credential.txt', '--choice', 'choice.json').rstrip(b'\n')
        ballot_path.write_bytes(ballot)
    election['api_ballot_file'] = str(ballot_path)
    lab.save()
    print(json.dumps({'mode': mode, 'public_archive_bytes': archive.stat().st_size, 'extra_api_ballot': 'prepared_offline'}), flush=True)
