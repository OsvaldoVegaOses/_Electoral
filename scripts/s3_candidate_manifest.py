"""Hash the reviewable Git candidate, excluding ignored runtime files and the manifest itself."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
DESTINATION='doc/Sprint_3/evidencias/candidato.json'

def manifest():
    output=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT)
    records=[]
    for name in sorted(set(output.decode('utf-8').split('\0'))-{'',DESTINATION}):
        path=ROOT/name
        if not path.is_file():
            raise RuntimeError('Candidate contains a missing file: '+name)
        records.append({'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    digest=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'base_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT).decode().strip(),
        'working_tree':True,'content_sha256':digest,'files':records,
        'exclusions':'Git-ignored files and this manifest; no runtime mail, keys, dumps or browser traces'}

if __name__=='__main__':
    document=manifest()
    destination=ROOT/DESTINATION
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(document['files']),'content_sha256':document['content_sha256']}))
