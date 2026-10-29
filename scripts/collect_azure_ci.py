"""Validate a sanitized ACR log summary; raw logs stay in ignored local runtime."""
import argparse
import base64
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--log-file',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--expected-sha',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    lines=Path(args.log_file).read_text(encoding='utf-8',errors='replace').splitlines()
    encoded=[line.split('AZURE_CI_SUMMARY ',1)[1].strip() for line in lines if 'AZURE_CI_SUMMARY ' in line]
    if len(encoded)!=1:raise SystemExit('Expected one complete CI summary; do not infer a pass from partial logs.')
    report=json.loads(base64.b64decode(encoded[0],validate=True))
    if report['source_sha']!=args.expected_sha or report['run_id']!=args.run_id or report['result']!='passed':
        raise SystemExit('CI identity/result mismatch')
    required={'synthetic-services','backend-migrations-concurrency-restore','frontend-lint','frontend-build',
        'e2e-real-http-postgresql','belenios-ui-api-doubles','python-dependency-audit','npm-dependency-audit',
        'secrets-current-and-history','compose-nginx'}
    if {s['name'] for s in report['stages']}!=required or any(s['result']!='passed' for s in report['stages']):
        raise SystemExit('A required stage is missing or failed')
    if report['backend']['skipped'] or report['backend']['failures'] or report['backend']['working_tree']:
        raise SystemExit('The required backend gate did not pass on a clean tree')
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_sha':report['source_sha'],'run_id':report['run_id'],
        'backend_tests':report['backend']['test_cases'],'e2e_tests':report['e2e_tests'],'stages':len(report['stages'])}))

if __name__=='__main__':main()
