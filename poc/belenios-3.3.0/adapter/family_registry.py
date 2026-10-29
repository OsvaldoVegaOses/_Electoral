"""Private synthetic H4 registry, outside Belenios and the TheoGen backend."""
import hashlib
import json
import re
import secrets


class RegistryError(ValueError):
    pass


class FamilyRegistry:
    def __init__(self, families):
        self.rows = []
        self.frozen = False
        family_ids, members = set(), set()
        for family in families:
            family_id, people = family['id'], family['members']
            if not re.fullmatch(r'fam-[0-9]{2}', family_id) or family_id in family_ids or not people:
                raise RegistryError('Explicit unique synthetic families are required')
            if len(people) != len(set(people)):
                raise RegistryError('Duplicate representative in a family')
            for person in people:
                if not re.fullmatch(r'rep[0-9]{2}[ab]?@ejemplo\.test', person) or person in members:
                    raise RegistryError('Only unique explicit synthetic representatives are supported')
                members.add(person)
            family_ids.add(family_id)
            self.rows.append({'id': family_id, 'members': list(people), 'representative': None,
                              'decision': None, 'ballot_identity': 'unit-' + secrets.token_hex(16) + '@ejemplo.test'})

    def select(self, family_id, representative, decision):
        if self.frozen:
            raise RegistryError('Frozen registry: representative changes require an incident and a new process')
        row = next((row for row in self.rows if row['id'] == family_id), None)
        if row is None or representative not in row['members'] or not re.fullmatch(r'poc-decision-[0-9]+', decision):
            raise RegistryError('An explicit member and synthetic recorded decision are required')
        row.update(representative=representative, decision=decision)

    def freeze(self):
        if any(row['representative'] is None for row in self.rows):
            raise RegistryError('Unresolved representation: do not provision credentials')
        self.frozen = True
        return self.ballot_identities()

    def ballot_identities(self):
        if not self.frozen:
            raise RegistryError('Freeze the approved registry before export')
        return [row['ballot_identity'] for row in self.rows]

    def identity_for(self, representative):
        if not self.frozen:
            raise RegistryError('Registry is not frozen')
        row = next((row for row in self.rows if row['representative'] == representative), None)
        if row is None:
            raise RegistryError('Representative not selected: no second family identity or credential')
        return row['ballot_identity']

    def summary(self):
        identities = self.ballot_identities()
        return {'synthetic_people': sum(len(row['members']) for row in self.rows), 'enabled_family_units': len(identities),
                'families_with_two_representatives': sum(len(row['members']) == 2 for row in self.rows),
                'public_roster_sha256': hashlib.sha256(json.dumps(identities, separators=(',', ':')).encode()).hexdigest()}
