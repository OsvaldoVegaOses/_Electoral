"""Exercise the actual POSIX entrypoint without a database or network."""
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize('environment,auto,action,expected,code',[
    ('production','false','serve',['uvicorn'],0),
    ('staging','false','serve',['uvicorn'],0),
    ('production','true','serve',[],64),
    ('development','true','serve',['alembic','uvicorn'],0),
    ('production','false','migrate',['alembic'],0),
])
def test_release_migration_is_separate_from_api_startup(tmp_path,environment,auto,action,expected,code):
    entrypoint=Path(__file__).resolve().parents[1]/'entrypoint.sh'
    (tmp_path/'entrypoint.sh').write_bytes(entrypoint.read_bytes().replace(b'\r\n',b'\n'))
    bindir=tmp_path/'bin';bindir.mkdir()
    for command in ('alembic','uvicorn'):
        stub=bindir/command
        stub.write_bytes(('#!/bin/sh\necho EXEC:'+command+'\n').encode())
        stub.chmod(0o755)
    command=['docker','run','--rm','--network','none','--entrypoint','/bin/sh',
        '--mount',f'type=bind,source={tmp_path},target=/contract,readonly',
        '-e','PATH=/contract/bin:/usr/local/bin:/usr/bin:/bin',
        '-e','ENVIRONMENT='+environment,'-e','RUN_MIGRATIONS_ON_STARTUP='+auto,
        os.getenv('S3_SHELL_TEST_IMAGE','postgres:16-alpine'),'/contract/entrypoint.sh',action]
    result=subprocess.run(command,capture_output=True,text=True,timeout=45)
    assert result.returncode==code,result.stderr
    assert [line[5:] for line in result.stdout.splitlines() if line.startswith('EXEC:')]==expected
