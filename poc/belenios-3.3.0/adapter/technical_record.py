"""Produce a public experimental record only after independently verifying its anchor."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from lab_adapter import AdapterError, LabAdapter


def create_record(adapter, report):
    anchor = report['elections']['single']
    evidence = adapter.verified_evidence('poc-h4-record', anchor['uuid'], anchor)
    families = report['family_summary']
    if evidence['enabled_units'] != families['enabled_family_units']:
        raise AdapterError('Frozen family universe does not match verified election')
    return {
        'schema': 'theogen-experimental-record/v1', 'status': 'PROTOTIPO_TECNICO_SIN_VALIDEZ_JURIDICA',
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'organization': 'Organizacion ficticia H4',
        'election': {'uuid': evidence['belenios_uuid'], 'policy_tested': 'R2: deny-revote at instance level',
                     'statutory_approval': 'PENDIENTE', 'family_representation_approval': 'PENDIENTE'},
        'universe': {'synthetic_people': families['synthetic_people'], 'enabled_units': evidence['enabled_units'],
                     'unit_type_tested': 'synthetic_family', 'frozen_public_roster_sha256': families['public_roster_sha256']},
        'tally': {'options': [{'label': label, 'votes': count} for label, count in zip(('Lista A', 'Lista B'), evidence['counts'])],
                  'counted_ballots': evidence['counted_ballots'], 'participation': evidence['participation'],
                  'blank': {'value': None, 'modeled': False, 'reason': 'One mandatory A/B selection; blank not offered'},
                  'null': {'value': None, 'modeled': False, 'reason': 'Invalid ballots are rejected; no null-vote category'},
                  'tie_resolution': 'PENDIENTE: no office allocation or winner inferred'},
        'quorum': {'required_ratio': None, 'assessed': False, 'reason': 'No institution-specific approved rule supplied'},
        'incidents': [{'type': 'R2_SECOND_CAST_REJECTED', 'active_units_after_attempt': evidence['counted_ballots']},
                      {'type': 'ALTERNATE_REPRESENTATIVES_NOT_GIVEN_ANOTHER_IDENTITY', 'units': families['families_with_two_representatives']}],
        'representation_and_incident_source': 'Local laboratory registry/browser reports; not a cryptographic or legal attestation',
        'evidence': evidence,
        'authorities': {'credential_authority': 'External CLI in a separate networkless process on the same host',
                        'trustees': 'Two of three external simulated custodians plus mandatory server component',
                        'independent_human_auditor': 'PENDIENTE'},
        'signatures': [], 'legal_review': 'PENDIENTE',
        'privacy': 'No representative addresses, family IDs, credentials, individual selections or private mappings in this record',
    }


def render_markdown(record):
    tally, evidence = record['tally'], record['evidence']
    options = '\n'.join(f"| {item['label']} | {item['votes']} |" for item in tally['options'])
    universe = record['universe']
    tie = 'Hay empate. ' if tally['options'][0]['votes'] == tally['options'][1]['votes'] else ''
    alternates = record['incidents'][1]['units']
    return f"""# Acta técnica experimental H4

**{record['status']}**. Organización ficticia; sin firmas ni aprobación de estatutos, quórum o representación familiar.

UUID: `{evidence['belenios_uuid']}`. {universe['synthetic_people']} apoderados ficticios, **{universe['enabled_units']} unidades familiares habilitadas**. {tally['counted_ballots']} votos computados; participación técnica: **{tally['participation']:.0%}**.

| Opción | Votos |
|---|---|
{options}

{tie}No se determina ganador, cargo o mecanismo de desempate. Blanco y nulo no se modelaron: su valor es **no aplicable**, no un cero escrutado. Quórum no evaluado por falta de regla institucional aprobada.

Se rechazó el segundo sufragio en la instancia R2. {alternates} representantes alternativos no recibieron otra identidad de unidad. La correspondencia familiar y la custodia de credenciales permanecen privadas. La representación e incidentes proceden de los registros locales de laboratorio, no de una certificación criptográfica o jurídica.

Archivo público SHA-256: `{evidence['public_archive_sha256']}`.

Cabeza final: `{evidence['final_event_hash']}`. Resultado: `{evidence['result_object_hash']}`.

Verificador Belenios 3.3.0, commit `{evidence['upstream_commit']}`; exit 0 en contenedor sin red, montando solo archivo público de lectura. El anclaje es local y no está firmado por un tercero.

Autoridad manual externa y trustees 2/3 simulados, más componente servidor; todos bajo el mismo host/operador. Auditor humano independiente, firmas y evaluación jurídica: **PENDIENTES**.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    record = create_record(LabAdapter('http://127.0.0.1:18002'), report)
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    args.output.with_suffix('.md').write_text(render_markdown(record), encoding='utf-8')
    print(json.dumps({'technical_record': 'PASS', 'counted_units': record['tally']['counted_ballots'], 'legally_valid': False}))


if __name__ == '__main__':
    main()
