"""Queue a public clean Git bundle using the SDK shipped with Azure CLI.

Unlike `az acr run --no-logs`, return the assigned ID before waiting for tests.
Temporary upload SAS URLs stay in memory and are never logged or saved.
"""
import argparse
import hashlib
import importlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SUBSCRIPTION='54ce7e6a-e909-4bef-b0cd-8133c2087dcf'
FILES={'Dockerfile','acr-task.yaml','source.bundle','source-manifest.json'}


def public_archive(context,sha):
    context=Path(context).resolve()
    if not re.fullmatch('[a-f0-9]{40}',sha) or {path.name for path in context.iterdir()}!=FILES:
        raise ValueError('Only the four public source context files may be submitted')
    for name in FILES:
        path=context/name
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(context):
            raise ValueError('Unsafe source context member')
    manifest=json.loads((context/'source-manifest.json').read_text(encoding='utf-8'))
    if (manifest['source_sha']!=sha or manifest['private_runtime_included'] is not False
            or manifest['bundle_sha256']!=hashlib.sha256((context/'source.bundle').read_bytes()).hexdigest()
            or sum((context/name).stat().st_size for name in FILES)>64*1024*1024):
        raise ValueError('Source context identity/size mismatch')
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as archive:
        for name in sorted(FILES):archive.add(context/name,arcname=name,recursive=False)
    return output.getvalue()


def client_and_models():
    from azure.cli.core import get_default_cli
    from azure.cli.core._profile import Profile
    from azure.cli.command_modules.acr._client_factory import cf_acr_registries_tasks
    cli=get_default_cli()
    if Profile(cli_ctx=cli).get_subscription()['id']!=SUBSCRIPTION:
        raise ValueError('The active subscription differs from the authorized registry')
    client=cf_acr_registries_tasks(cli)
    models=importlib.import_module(type(client).__module__.split('.operations',1)[0]+'.models')
    for name in ('FileTaskRunRequest','SetValue','PlatformProperties','AgentProperties'):
        getattr(models,name)
    return client,models


def submit(context,sha,timeout):
    data=public_archive(context,sha)
    if not 300<=timeout<=2400:raise ValueError('Invalid CI timeout')
    client,models=client_and_models()
    upload=client.get_build_source_upload_url(resource_group_name='new',registry_name='theogenongtcacr')
    destination=urlsplit(upload.upload_url)
    if (destination.scheme!='https' or not destination.hostname
            or not destination.hostname.endswith('.blob.core.windows.net') or destination.username
            or destination.password or destination.fragment):raise ValueError('Untrusted upload destination')
    request=Request(upload.upload_url,data=data,method='PUT',headers={'x-ms-blob-type':'BlockBlob'})
    with urlopen(request,timeout=120) as response:
        if response.status!=201:raise ValueError('Upload not confirmed')
    body=models.FileTaskRunRequest(task_file_path='acr-task.yaml',source_location=upload.relative_path,
        values=[models.SetValue(name='expected_sha',value=sha,is_secret=False)],timeout=timeout,
        platform=models.PlatformProperties(os='Linux',architecture='amd64'),
        agent_configuration=models.AgentProperties(cpu=2))
    run=client.schedule_run(resource_group_name='new',registry_name='theogenongtcacr',run_request=body)
    if not re.fullmatch('[a-zA-Z0-9_-]+',run.run_id):raise ValueError('Run ID not confirmed')
    return {'run_id':run.run_id,'source_sha':sha}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--context')
    parser.add_argument('--sha')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--timeout',type=int,default=2400)
    args=parser.parse_args()
    try:
        if args.preflight:
            client_and_models()
            print(json.dumps({'sdk':'ready','subscription':SUBSCRIPTION}))
        elif args.context and args.sha:
            print(json.dumps(submit(args.context,args.sha,args.timeout)))
        else:parser.error('Provide --preflight or --context and --sha')
    except Exception as error:
        # Even network exception strings may embed a SAS URL: never print them.
        print(json.dumps({'error':type(error).__name__,'details':'Submission not confirmed; reconcile Azure before retrying'}))
        sys.exit(1)
