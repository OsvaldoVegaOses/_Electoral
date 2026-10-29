"""Refresh an Entra access token for each new PostgreSQL connection."""
import os
from sqlalchemy import event


def configure_azure_identity(engine):
    if os.getenv('AZURE_POSTGRES_IDENTITY_ENABLED', 'false').lower() != 'true':
        return
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('Azure PostgreSQL identity requires PostgreSQL')
    from azure.identity import ManagedIdentityCredential
    import certifi
    credential = ManagedIdentityCredential(client_id=os.environ['AZURE_CLIENT_ID'])

    @event.listens_for(engine, 'do_connect')
    def authenticate(dialect, connection_record, args, params):
        params['password'] = credential.get_token('https://ossrdbms-aad.database.windows.net/.default').token
        params['sslmode'] = 'verify-full'
        params['sslrootcert'] = certifi.where()
