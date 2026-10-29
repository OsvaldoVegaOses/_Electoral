"""Exercise the actual POSIX entrypoint without a database or network."""
import os
from pathlib import Path
import subprocess
import io
import tarfile

import pytest


@pytest.mark.parametrize('environment,auto,action,expected,code',[
    ('production','false','serve',['uvicorn'],0),
    ('staging','false','serve',['uvicorn'],0),
    ('production','true','serve',[],64),
    ('development','true','serve',['alembic','uvicorn'],0),
    ('production','false','migrate',['alembic'],0),
])
def test_release_migration_is_separate_from_api_startup(environment,auto,action,expected,code):
    entrypoint=Path(__file__).resolve().parents[1]/'entrypoint.sh'
    # Stream the contract instead of binding a path from inside a CI container.
    # The same real shell entrypoint is exercised on local and remote daemons.
    payload=io.BytesIO()
    with tarfile.open(fileobj=payload,mode='w') as archive:
        files={'entrypoint.sh':entrypoint.read_bytes().replace(b'\r\n',b'\n')}
        files.update({f'bin/{name}':f'#!/bin/sh\necho EXEC:{name}\n'.encode() for name in ('alembic','uvicorn')})
        for name,data in files.items():
            member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o755
            archive.addfile(member,io.BytesIO(data))
    command=['docker','run','--rm','-i','--network','none','--entrypoint','/bin/sh',
        '-e','ENVIRONMENT='+environment,'-e','RUN_MIGRATIONS_ON_STARTUP='+auto,
        os.getenv('S3_SHELL_TEST_IMAGE','postgres:16-alpine'),'-c',
        'mkdir /contract && tar -xf - -C /contract && export PATH=/contract/bin:$PATH && exec /bin/sh /contract/entrypoint.sh "$1"',
        'contract',action]
    result=subprocess.run(command,input=payload.getvalue(),capture_output=True,timeout=45)
    assert result.returncode==code,result.stderr.decode()
    assert [line[5:] for line in result.stdout.decode().splitlines() if line.startswith('EXEC:')]==expected
