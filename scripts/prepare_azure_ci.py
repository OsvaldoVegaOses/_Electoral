"""Package only a clean, committed Git tree for a one-shot Azure ACR CI run."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if git('status','--porcelain').strip():
        raise SystemExit('Commit or isolate pending changes before packaging CI; no dirty source is uploaded.')
    sha=git('rev-parse','HEAD').decode().strip()
    output=Path(args.output).resolve()
    if output.exists():raise SystemExit('Use a new output directory for every submission.')
    output.mkdir(parents=True)
    for original,destination in [('ci/azure/Dockerfile','Dockerfile'),('ci/azure/acr-task.yaml','acr-task.yaml')]:
        (output/destination).write_bytes(git('show',sha+':'+original))
    subprocess.run(['git','bundle','create',str(output/'source.bundle'),'HEAD'],cwd=ROOT,check=True)
    subprocess.run(['git','bundle','verify',str(output/'source.bundle')],cwd=ROOT,check=True,capture_output=True)
    report={'source_sha':sha,'bundle_sha256':hashlib.sha256((output/'source.bundle').read_bytes()).hexdigest(),
        'files':['Dockerfile','acr-task.yaml','source.bundle'],'private_runtime_included':False,
        'submission_nonce':uuid4().hex}
    (output/'source-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'context':str(output),'source_sha':sha,'bundle_sha256':report['bundle_sha256']}))

if __name__=='__main__':main()
