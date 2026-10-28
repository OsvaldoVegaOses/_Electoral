"""Verify H0 source evidence with Git and Python only; never execute Belenios."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--belenios', type=Path, required=True)
    parser.add_argument('--theogen', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('h0-2026-10-28.json').read_text(encoding='utf-8'))

    def git(repo, *command):
        return subprocess.check_output(['git', '-C', str(repo), *command])

    def require(condition, message):
        if not condition:
            raise SystemExit('FAIL: ' + message)

    def verify(repo, item):
        spec = item['commit'] + ':' + item['path']
        data = git(repo, 'show', spec)
        require(git(repo, 'rev-parse', spec).decode().strip() == item['git_blob_sha1'], spec + ' blob')
        require(hashlib.sha256(data).hexdigest() == item['sha256'], spec + ' sha256')
        require(len(data) == item['bytes'], spec + ' size')
        return data.decode('utf-8')

    expected = manifest['belenios']
    require(git(args.belenios, 'rev-parse', 'refs/tags/3.3.0').decode().strip() == expected['tag_object'], 'tag object')
    require(git(args.belenios, 'rev-parse', 'refs/tags/3.3.0^{}').decode().strip() == expected['commit'], 'peeled commit')
    sources = {item['path']: verify(args.belenios, item) for item in manifest['upstream_sources']}
    for item in manifest['comparison_only']['sources']:
        verify(args.belenios, item)
    for item in manifest['theogen_sources']:
        verify(args.theogen, item)
    comparison = manifest['comparison_only']['commit']
    diff = git(args.belenios, 'diff', expected['commit'], comparison, '--', 'doc/API.md')
    require(hashlib.sha256(diff).hexdigest() == manifest['comparison_only']['api_doc_diff_sha256'], 'API diff')

    probes = [
        ('VERSION', '3.3.0'),
        ('src/web/server/common/api_generic.ml', 'api_version = 6;'),
        ('src/web/server/common/web_config.ml', 'let deny_revote = ref false'),
        ('src/web/server/common/web_main.ml', 'Web_config.deny_revote := true'),
        ('src/web/server/common/web_persist.ml', 'if !Web_config.deny_revote then return @@ Error `RevoteNotAllowed'),
        ('src/web/server/common/api_elections.ml', 'return_json 401 (Yojson.Safe.to_string json)'),
        ('src/web/server/common/site_voter.ml', 'Api_elections.cast_ballot'),
        ('src/web/server/filesystem/election_ops.ml', 'S.set (Election (uuid, State)) Value `Closed'),
        ('src/web/server/filesystem/election_ops.ml', '[ `Single server_public_key; `Pedersen tp ]'),
        ('src/web/server/filesystem/main.ml', '[ "voters.txt"; "records" ]'),
        ('src/web/server/common/api_generic.ml', 'if sha256_b64 current = x then cont () else precondition_failed'),
        ('src/tool/tool_archive_pull.ml', 'objects/%s'),
        ('tests/tool/demo-threshold.sh', 'threshold=2'),
        ('tests/tool/demo-threshold.sh', 'trustees=3'),
    ]
    for path, fragment in probes:
        require(fragment in sources[path], path + ': ' + fragment)
    require('deny_revote' not in sources['src/web/api/serializable.atd'], 'no draft revote flag')
    require('handle_ifmatch' not in sources['src/web/server/common/api_credentials.ml'], 'credential If-Match coverage')
    require('[ "election" ]' not in sources['src/web/server/common/api_drafts.ml'], 'no draft/election dispatcher')
    require('email_verified' not in sources['src/web/api/serializable.atd'], 'OIDC userinfo schema')
    tree = git(args.belenios, 'ls-tree', '-r', '--name-only', expected['commit']).decode().splitlines()
    require('src/common/api/serializable.atd' not in tree, 'obsolete ATD path')
    print('PASS: 51 fixed-version sources, 4 comparison sources, 3 TheoGen base sources, tag/commit, API diff and 19 static probes.')
    print('Scope: source evidence only. No build, server, election or cryptographic verifier executed.')


if __name__ == '__main__':
    main()
