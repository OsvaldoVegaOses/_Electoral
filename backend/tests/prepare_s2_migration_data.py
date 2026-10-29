import os

import psycopg2


def main() -> None:
    database_url = os.environ["S2_MIGRATION_DATABASE_URL"]
    with psycopg2.connect(database_url.replace("postgresql+psycopg2://", "postgresql://", 1)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO schools (id, nombre) VALUES (1, 'Synthetic Migration School')")
            cursor.execute(
                """
                INSERT INTO elections
                    (id, nombre, school_id, tipo_votacion, regla_votacion, estado)
                VALUES
                    (1, 'Family With Complete Roster', 1, 'Test', 'Un voto por familia', 'Finalizada'),
                    (2, 'Family With Incomplete Roster', 1, 'Test', 'Un voto por familia', 'Finalizada'),
                    (3, 'Family With Existing Entitlements', 1, 'Test', 'Un voto por familia', 'Finalizada')
                """
            )
            cursor.execute(
                """
                INSERT INTO voters
                    (rut, rut_normalizado, nombre, familia_id, estado, election_id)
                VALUES
                    ('SYNTH-1', 'SYNTH-1', 'Synthetic 1', 'FAM-A', 'Pendiente', 1),
                    ('SYNTH-2', 'SYNTH-2', 'Synthetic 2', 'FAM-A', 'Pendiente', 1),
                    ('SYNTH-3', 'SYNTH-3', 'Synthetic 3', 'FAM-A', 'Pendiente', 1),
                    ('SYNTH-4', 'SYNTH-4', 'Synthetic 4', 'FAM-B', 'Pendiente', 1),
                    ('SYNTH-5', 'SYNTH-5', 'Synthetic 5', 'FAM-B', 'Pendiente', 1),
                    ('SYNTH-6', 'SYNTH-6', 'Synthetic 6', 'FAM-A', 'Pendiente', 2),
                    ('SYNTH-7', 'SYNTH-7', 'Synthetic 7', NULL, 'Pendiente', 2),
                    ('SYNTH-8', 'SYNTH-8', 'Synthetic 8', 'FAM-C', 'Pendiente', 3)
                """
            )
            cursor.execute(
                """
                INSERT INTO voting_entitlements (election_id, unit_key, estado)
                VALUES (3, 'FAM:LEGACY-UNIT', 'Consumido')
                """
            )
            cursor.execute("UPDATE voting_entitlements SET voter_id_consumidor=8 WHERE election_id=3")
            cursor.execute("UPDATE voters SET estado='Votó' WHERE id=8")
            cursor.execute("INSERT INTO candidates (id,nombre,election_id) VALUES (1,'Synthetic Option',3)")
            cursor.execute("INSERT INTO votes (candidate_id,voter_id,election_id,hash_integridad) "
                           "VALUES (1,8,3,'s2-synthetic-recognized-vote')")


if __name__ == "__main__":
    main()
