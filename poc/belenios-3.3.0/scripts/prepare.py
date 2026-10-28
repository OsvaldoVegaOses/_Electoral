"""Prepare an exact Git archive and local lab assets, without executing upstream code."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

COMMIT = '337887bd1862c7cd057080b530fd80941bfc3c69'
TAG = '2f0c5eb950d964baeea95f81ff6db7c418020ba5'
ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    def git(*command):
        return subprocess.check_output(['git', '-c', f'safe.directory={source.as_posix()}', '-c', 'core.autocrlf=false', '-C', str(source), *command])
    if git('rev-parse', 'refs/tags/3.3.0^{}').decode().strip() != COMMIT or git('rev-parse', 'refs/tags/3.3.0').decode().strip() != TAG:
        raise SystemExit('Upstream tag/commit mismatch')
    build = ROOT / '.runtime/build'
    build.mkdir(parents=True, exist_ok=True)
    archive = git('archive', '--format=tar', COMMIT)
    (build / 'source.tar').write_bytes(archive)
    (build / 'MANIFEST').write_bytes(git('ls-tree', '-r', '--name-only', COMMIT))
    (build / 'GIT_LOG').write_bytes(git('log', '-1', '--format=%H %s', COMMIT))
    epoch = git('show', '-s', '--format=%ct', COMMIT).decode().strip()
    (build / 'SOURCE_DATE_EPOCH').write_text(epoch + '\n', encoding='ascii')
    (build / 'assets').mkdir(exist_ok=True)
    for path in [*(ROOT / 'scripts').glob('*.sh'), ROOT / 'scripts/ingress.js']:
        (build / 'assets' / path.name).write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    shutil.copyfile(ROOT / 'Dockerfile.poc', build / 'Dockerfile.poc')
    result = {'commit': COMMIT, 'tag': TAG, 'source_date_epoch': epoch,
              'source_tar_sha256': hashlib.sha256(archive).hexdigest(),
              'base_image': 'glondu/beleniosbase@sha256:3d57d508592aa94124473052e0beefcb6c06408fcbb1ded99febd6e70c4e7b62'}
    (ROOT / '.runtime/source.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
