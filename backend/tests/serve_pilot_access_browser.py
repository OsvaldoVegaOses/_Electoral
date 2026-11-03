"""Isolated browser fixture: synthetic account, no native bridge or mail access."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from services.pilot_access import Portal,server

with tempfile.TemporaryDirectory(prefix='pilot-browser-') as directory:
    origin='https://pilot.example.invalid'
    portal=Portal(directory,origin)
    portal.provision('member@example.invalid','Synthetic member','trustee',
                     'Synthetic-Initial-2026',origin+'/trustee#synthetic-role-reference')
    http=server(('127.0.0.1',0),portal)
    print(json.dumps({'port':http.server_port}),flush=True)
    try:http.serve_forever()
    finally:http.server_close()
