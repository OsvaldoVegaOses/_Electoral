import { useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Stack, Typography } from '@mui/material';
import { credentialDeliveryService } from '../services/api';

export default function CredentialDeliveriesPanel({ election, voters }) {
  const [operations, setOperations] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (election.motor === 'belenios' || election.estado !== 'Borrador') return null;
  async function act(voter, action) {
    setBusy(true); setError('');
    try {
      if (action) await action();
      const rows = await credentialDeliveryService.list(election.id, voter.id);
      setOperations(previous => ({ ...previous, [voter.id]: rows }));
    } catch (err) { setError(err.response?.data?.detail || 'No se confirmó la operación. Consulte su estado antes de enviar otra.'); }
    finally { setBusy(false); }
  }
  return <Card sx={{ my: 2 }}><CardContent>
    <Typography variant="h6">Entrega de credenciales MVP</Typography>
    <Alert severity="info">La credencial anterior se conserva hasta confirmar la entrega. Una respuesta incierta se concilia; no se reenvía automáticamente.</Alert>
    {voters.map(voter => <Box key={voter.id} sx={{ my: 2 }}>
      <Typography>{voter.nombre}</Typography>
      <Stack direction="row" spacing={1}>
        <Button disabled={busy || !voter.correo} onClick={() => {
          if (window.confirm('¿Confirma enviar o reemitir la credencial al correo registrado?')) {
            act(voter, () => credentialDeliveryService.issue(election.id, voter.id, crypto.randomUUID()));
          }
        }}>Enviar o reemitir</Button>
        <Button disabled={busy} onClick={() => act(voter)}>Consultar entrega</Button>
      </Stack>
      {(operations[voter.id] || []).map(operation => <Stack key={operation.operation_id} direction="row" spacing={1}>
        <Typography>{operation.status}</Typography>
        {['PENDING', 'ACCEPTED', 'UNKNOWN'].includes(operation.status) && <Button disabled={busy}
          onClick={() => act(voter, () => credentialDeliveryService.reconcile(election.id, voter.id, operation.operation_id))}>Conciliar con proveedor</Button>}
      </Stack>)}
    </Box>)}
    {error && <Alert severity="error">{error}</Alert>}
  </CardContent></Card>;
}
