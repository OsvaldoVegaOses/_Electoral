"""Package the exact upstream tag for release; never package runtime/private data."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

COMMIT="337887bd1862c7cd057080b530fd80941bfc3c69"
TAG="2f0c5eb950d964baeea95f81ff6db7c418020ba5"
ROOT=Path(__file__).resolve().parents[1]


def prepare(source, output):
    source=Path(source).resolve(); output=Path(output).resolve()
    def git(*args):return subprocess.check_output(["git","-c","core.autocrlf=false","-C",str(source),*args])
    if git("rev-parse","refs/tags/3.3.0^{}").decode().strip()!=COMMIT or git("rev-parse","refs/tags/3.3.0").decode().strip()!=TAG:
        raise ValueError("Unexpected upstream tag/commit")
    if git("status","--porcelain").strip():raise ValueError("Upstream source is dirty")
    output.mkdir(parents=True,exist_ok=False)
    archive=git("archive","--format=tar",COMMIT)
    (output/"source.tar").write_bytes(archive)
    for name,command in (("MANIFEST",("ls-tree","-r","--name-only",COMMIT)),("GIT_LOG",("log","-1","--format=%H %s",COMMIT)),("SOURCE_DATE_EPOCH",("show","-s","--format=%ct",COMMIT))):
        (output/name).write_bytes(git(*command))
    for origin,name in (("deploy/belenios-release/Dockerfile","Dockerfile"),("deploy/belenios-release/entrypoint.py","entrypoint.py")):
        (output/name).write_bytes((ROOT/origin).read_bytes().replace(b"\r\n",b"\n"))
    report={"upstream_commit":COMMIT,"tag_object":TAG,"source_tar_sha256":hashlib.sha256(archive).hexdigest(),
            "build_target":"build-release-server","private_runtime_included":False}
    (output/"source-manifest.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--source",required=True);parser.add_argument("--output",required=True);args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.output)))
