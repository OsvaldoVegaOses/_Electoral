import { useMemo, useState } from 'react';
import { Alert, Box, Button, Card, CardContent, Checkbox, FormControlLabel, MenuItem, Stack, TextField, Typography } from '@mui/material';
import { beleniosService } from '../services/api';

const actions = {
  Draft: [['ValidateElection', 'Validar preparación externa']],
  Closed: [['Open', 'Abrir en Belenios'], ['ComputeEncryptedTally', 'Preparar escrutinio']],
  Open: [['Close', 'Cerrar en Belenios']],
  EncryptedTally: [['ReleaseTally', 'Publicar escrutinio de trustees']],
};

function download(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default function BeleniosPanel({ election, voters, engine, onRefresh }) {
  const [policy, setPolicy] = useState('');
  const [approval, setApproval] = useState('');
  const [selected, setSelected] = useState({});
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [anchor, setAnchor] = useState({ final_event_hash: '', result_object_hash: '', archive_sha256: '', anchor_reference: '' });
  const [remoteUuid, setRemoteUuid] = useState('');
  const groups = useMemo(() => {
    const result = {};
    for (const voter of voters) {
      const key = election.regla_votacion === 'Un voto por familia' ? (voter.familia_id || '').trim().toUpperCase() : String(voter.id);
      (result[key || 'SIN UNIDAD'] ||= []).push(voter);
    }
    return Object.entries(result);
  }, [election.regla_votacion, voters]);
  const binding = engine?.binding;
  if (!engine || (!engine.enabled && !binding)) return null;
  async function act(fn) {
    setBusy(true); setError('');
    try { await fn(); } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Revise los datos o consulte el estado antes de repetir la operación.');
    } finally {
      try { await onRefresh(); } catch { setError('No se pudo actualizar el estado. Coteje la elección antes de repetir una operación.'); }
      setBusy(false);
    }
  }
  const representatives = groups.map(([key]) => Number(selected[key])).filter(Boolean);
  return <Card sx={{ my: 3 }} data-testid="belenios-panel"><CardContent>
    <Typography variant="h5" component="h2">Motor Belenios</Typography>
    <Alert severity="info" sx={{ my: 2 }}>Integración de laboratorio con datos ficticios. El voto se realiza directamente en Belenios; TheoGen no recibe la selección ni las claves privadas.</Alert>
    {!engine.enabled && <Alert severity="warning">Las operaciones del motor están deshabilitadas. La elección conserva su vinculación y no puede usar la urna MVP.</Alert>}
    {!binding ? <Stack spacing={2}>
      <Typography>Seleccione la política y un representante por unidad. Después de preparar la elección, padrón y opciones quedan congelados.</Typography>
      <TextField select label="Política de voto" value={policy} onChange={e => setPolicy(e.target.value)}>
        <MenuItem value="R1">R1: cuenta el último voto válido</MenuItem><MenuItem value="R2">R2: se rechaza un segundo voto</MenuItem>
      </TextField>
      <TextField label="Referencia de aprobación de la comisión" value={approval} onChange={e => setApproval(e.target.value)} helperText="Use una referencia, sin RUT, nombres o secretos." />
      {groups.map(([key, people], index) => <TextField key={key} select label={`Representante de unidad ${index + 1}`} value={selected[key] || ''} onChange={e => setSelected({ ...selected, [key]: e.target.value })}>
        {people.map(person => <MenuItem key={person.id} value={person.id}>{person.nombre}</MenuItem>)}
      </TextField>)}
      <FormControlLabel control={<Checkbox checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />} label="Ensayo ficticio con una selección obligatoria por boleta; blanco y nulo no se modelan." />
      <Button variant="contained" disabled={busy || !confirmed || !policy || !approval || representatives.length !== groups.length || !groups.length} onClick={() => act(() => beleniosService.prepare(election.id, {
        request_id: crypto.randomUUID(), policy, representative_ids: representatives, approval_ref: approval,
        ballot_mode: 'mandatory_single_choice_no_blank_no_null', synthetic_laboratory: true,
      }))}>Preparar elección en Belenios</Button>
    </Stack> : <Stack spacing={2}>
      <Typography>Política: {binding.policy} · Estado confirmado: {binding.phase}</Typography>
      <Typography>{binding.total_people} personas · {binding.total_units} unidades habilitadas</Typography>
      {binding.uuid && <Typography>Identificador Belenios: {binding.uuid}</Typography>}
      <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>
        {binding.public_url && <Button href={binding.public_url} target="_blank" rel="noopener noreferrer">Abrir urna Belenios</Button>}
        {binding.admin_url && <Button href={binding.admin_url} target="_blank" rel="noopener noreferrer">Administración y autoridades</Button>}
        <Button disabled={busy} onClick={() => act(async () => download(await beleniosService.units(election.id), 'correspondencia-privada-unidades.json'))}>Exportar correspondencia privada</Button>
      </Stack>
      <Alert severity="warning">La correspondencia es privada. Entregue credenciales por una autoridad separada; no las cargue en TheoGen. Complete la ceremonia de trustees 2 de 3 en Belenios.</Alert>
      {binding.inflight || binding.phase === 'UNKNOWN' ? <Box>
        <Alert severity="error">Operación pendiente o desconocida. No la repita. Coteje el proveedor antes de reconciliar.</Alert>
        <TextField fullWidth sx={{ my: 2 }} label="UUID remoto cotejado (si falta)" value={remoteUuid} onChange={e => setRemoteUuid(e.target.value)} />
        <Button disabled={busy || !engine.enabled} onClick={() => {
          if (window.confirm('¿Cotejó manualmente la operación y el estado de Belenios? Esta acción solo adopta un estado remoto coincidente.')) act(() => beleniosService.reconcile(election.id, { operation_id: binding.inflight, candidate_uuid: binding.uuid || remoteUuid, manually_reviewed: true }));
        }}>Reconciliar estado cotejado</Button>
      </Box> : <Stack direction="row" spacing={2} sx={{ flexWrap: 'wrap' }}>{(actions[binding.phase] || []).filter(([action]) => !binding.available_actions || binding.available_actions.includes(action)).map(([action, label]) => <Button key={action} disabled={busy || !engine.enabled} onClick={() => {
        if (window.confirm(`¿Confirma la operación «${label}» para esta elección de laboratorio?`)) act(() => beleniosService.transition(election.id, action));
      }}>{label}</Button>)}</Stack>}
      {binding.phase === 'Tallied' && <Stack spacing={2}>
        <Typography>Ingrese las huellas finales revisadas por el auditor para verificar y contrastar el resultado.</Typography>
        {Object.keys(anchor).map(key => <TextField key={key} label={({final_event_hash:'Huella del evento final',result_object_hash:'Huella del resultado',archive_sha256:'SHA-256 del archivo público',anchor_reference:'Referencia del anclaje revisado'})[key]} value={anchor[key]} onChange={e => setAnchor({ ...anchor, [key]: e.target.value })} />)}
        <Button disabled={busy || !engine.enabled || Object.values(anchor).some(v => !v)} onClick={() => act(() => beleniosService.verify(election.id, anchor))}>Verificar resultado y archivo público</Button>
      </Stack>}
      {binding.result && <Box data-testid="belenios-verified-result">
        <Typography variant="h6">Resultado verificado</Typography>
        {binding.result.options.map((option, i) => <Typography key={i}>{option.label}: {option.votes}</Typography>)}
        <Typography>{binding.result.counted_ballots} votos computados de {binding.result.enabled_units} unidades · {(binding.result.participation * 100).toFixed(1)} %</Typography>
        <Alert severity="warning">Expediente técnico experimental. Quórum, estatutos, firmas y custodia independiente no acreditados.</Alert>
        <Button onClick={() => download(binding.result, `resultado-verificado-${binding.uuid}.json`)}>Descargar expediente técnico</Button>
      </Box>}
    </Stack>}
    {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
  </CardContent></Card>;
}
