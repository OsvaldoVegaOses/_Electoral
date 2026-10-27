import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Tabs,
  Tab,
  Button,
  Grid,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  IconButton,
  Tooltip,
  LinearProgress,
  Divider,
} from '@mui/material';
import { useParams, Link, useLocation } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import LockIcon from '@mui/icons-material/Lock';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DownloadIcon from '@mui/icons-material/Download';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EmailIcon from '@mui/icons-material/Email';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import RefreshIcon from '@mui/icons-material/Refresh';
import DeleteIcon from '@mui/icons-material/Delete';

import {
  electionService,
  voterService,
  candidateService,
  reportService,
} from '../services/api';
import StatusBadge from '../components/StatusBadge';

const ElectionDetail = () => {
  const { id } = useParams();
  const location = useLocation();

  // Tab State: si viene con hash #escrutinio abre tab 3
  const [tabIndex, setTabIndex] = useState(() => {
    if (location.hash === '#escrutinio') return 3;
    if (location.hash === '#credenciales') return 2;
    return 0;
  });

  const [election, setElection] = useState(null);
  const [voters, setVoters] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [scrutiny, setScrutiny] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionSuccess, setActionSuccess] = useState('');
  const [actionError, setActionError] = useState('');

  // Modales
  const [openUploadModal, setOpenUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);

  const [openAddVoterModal, setOpenAddVoterModal] = useState(false);
  const [newVoter, setNewVoter] = useState({ rut: '', nombre: '', curso: '', correo: '', familia_id: '' });

  const [openAddCandidateModal, setOpenAddCandidateModal] = useState(false);
  const [newCandidate, setNewCandidate] = useState({ nombre: '', cargo: '', descripcion: '', foto: '' });

  const [openEmailModal, setOpenEmailModal] = useState(false);
  const [emailSimulationData, setEmailSimulationData] = useState(null);

  const [openAddCommitteeModal, setOpenAddCommitteeModal] = useState(false);
  const [newCommittee, setNewCommittee] = useState({ nombre: '', rut: '', correo: '', cargo: 'Vocal de Control' });

  const [voterSearch, setVoterSearch] = useState('');

  useEffect(() => {
    loadAllData();
  }, [id]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      const [elData, vData, cData] = await Promise.all([
        electionService.getById(id),
        voterService.getByElection(id),
        candidateService.getByElection(id),
      ]);
      setElection(elData);
      setVoters(vData);
      setCandidates(cData);

      // A2 - P0: Solo solicitar escrutinio si la elección está formalmente cerrada
      if (elData.estado === 'Cerrada' || elData.estado === 'Finalizada') {
        try {
          const scData = await reportService.getScrutiny(id);
          setScrutiny(scData);
        } catch {
          setScrutiny(null);
        }
      } else {
        setScrutiny(null);
      }
    } catch (err) {
      console.error(err);
      setActionError('Error al cargar información de la elección.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadActaApertura = async () => {
    try {
      const cleanName = election?.nombre ? election.nombre.replace(/[^a-zA-Z0-9_-]/g, '_') : id;
      await reportService.downloadActaAperturaPdf(id, `Acta_Apertura_${cleanName}.pdf`);
      setActionSuccess('Acta de apertura descargada exitosamente.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al descargar acta de apertura.');
    }
  };

  const handleDownloadActaCierre = async () => {
    try {
      const cleanName = election?.nombre ? election.nombre.replace(/[^a-zA-Z0-9_-]/g, '_') : id;
      await reportService.downloadActaCierrePdf(id, `Acta_Cierre_${cleanName}.pdf`);
      setActionSuccess('Acta de cierre descargada exitosamente.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al descargar acta de cierre.');
    }
  };

  const handleOpenElection = async () => {
    try {
      const updated = await electionService.open(id);
      setElection(updated);
      setActionSuccess('¡Elección abierta con éxito! Se han emitido los tokens UUID para todos los electores.');
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al abrir la elección.');
    }
  };

  const handleCloseElection = async () => {
    if (!window.confirm('¿Está seguro de cerrar formalmente esta elección? La urna digital será sellada para escrutinio definitivo.')) {
      return;
    }
    try {
      const updated = await electionService.close(id);
      setElection(updated);
      setActionSuccess('Elección cerrada formalmente. El escrutinio final se encuentra consolidado.');
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al cerrar la elección.');
    }
  };

  // Upload Excel / CSV
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadFile) return;

    setUploadLoading(true);
    setUploadResult(null);
    try {
      const res = await voterService.uploadExcel(id, uploadFile);
      setUploadResult(res);
      setActionSuccess(`Padrón procesado: ${res.insertados} electores incorporados con éxito.`);
      const vData = await voterService.getByElection(id);
      setVoters(vData);
      const scData = await reportService.getScrutiny(id);
      setScrutiny(scData);
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al cargar el archivo de padrón.');
    } finally {
      setUploadLoading(false);
    }
  };

  // Crear votante individual
  const handleCreateVoter = async (e) => {
    e.preventDefault();
    try {
      await voterService.create(id, newVoter);
      setActionSuccess(`Elector ${newVoter.nombre} agregado exitosamente.`);
      setOpenAddVoterModal(false);
      setNewVoter({ rut: '', nombre: '', curso: '', correo: '', familia_id: '' });
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al crear elector.');
    }
  };

  // Crear candidato
  const handleCreateCandidate = async (e) => {
    e.preventDefault();
    try {
      await candidateService.create(id, {
        ...newCandidate,
        orden: candidates.length + 1,
      });
      setActionSuccess(`Candidato/Lista '${newCandidate.nombre}' creado exitosamente.`);
      setOpenAddCandidateModal(false);
      setNewCandidate({ nombre: '', cargo: '', descripcion: '', foto: '' });
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al crear candidato.');
    }
  };

  // Eliminar candidato
  const handleDeleteCandidate = async (candId) => {
    if (!window.confirm('¿Está seguro de eliminar este candidato?')) return;
    try {
      await candidateService.delete(id, candId);
      setActionSuccess('Candidato eliminado con éxito.');
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'No se pudo eliminar el candidato.');
    }
  };

  // Simular correos
  const handleSimulateEmails = async () => {
    try {
      const data = await voterService.getEmailSimulation(id);
      setEmailSimulationData(data);
      setOpenEmailModal(true);
    } catch (err) {
      setActionError('Error al generar simulación de despacho.');
    }
  };

  // Agregar miembro de comisión
  const handleAddCommittee = async (e) => {
    e.preventDefault();
    try {
      await electionService.addCommitteeMember(id, newCommittee);
      setActionSuccess(`Miembro ${newCommittee.nombre} incorporado a la Comisión Electoral.`);
      setOpenAddCommitteeModal(false);
      setNewCommittee({ nombre: '', rut: '', correo: '', cargo: 'Vocal de Control' });
      loadAllData();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Error al agregar miembro.');
    }
  };

  const copyToClipboard = (text, label = 'Copiado al portapapeles') => {
    navigator.clipboard.writeText(text);
    setActionSuccess(label);
    setTimeout(() => setActionSuccess(''), 3000);
  };

  const filteredVoters = voters.filter(
    (v) =>
      v.nombre.toLowerCase().includes(voterSearch.toLowerCase()) ||
      v.rut.toLowerCase().includes(voterSearch.toLowerCase()) ||
      (v.curso && v.curso.toLowerCase().includes(voterSearch.toLowerCase())) ||
      (v.familia_id && v.familia_id.toLowerCase().includes(voterSearch.toLowerCase()))
  );

  if (loading || !election) {
    return (
      <Box sx={{ width: '100%', mt: 4 }}>
        <LinearProgress sx={{ color: '#0d233a' }} />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Breadcrumb y Volver */}
      <Box sx={{ mb: 3 }}>
        <Button component={Link} to="/elecciones" startIcon={<ArrowBackIcon />} sx={{ color: 'text.secondary', mb: 1 }}>
          Volver al Listado
        </Button>
      </Box>

      {/* Alertas Globales */}
      {actionSuccess && (
        <Alert severity="success" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setActionSuccess('')}>
          {actionSuccess}
        </Alert>
      )}
      {actionError && (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }} onClose={() => setActionError('')}>
          {actionError}
        </Alert>
      )}

      {/* Header Card de la Elección */}
      <Card sx={{ mb: 4, borderRadius: 3, boxShadow: '0 4px 20px rgba(13, 35, 58, 0.08)' }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 2, mb: 2 }}>
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
                <StatusBadge status={election.estado} size="medium" />
                <Chip label={election.tipo_votacion} size="small" variant="outlined" sx={{ fontWeight: 600 }} />
                <Chip
                  label={`Regla: ${election.regla_votacion}`}
                  size="small"
                  sx={{
                    backgroundColor: election.regla_votacion.includes('familia') ? '#fdf4ff' : '#eff6ff',
                    color: election.regla_votacion.includes('familia') ? '#86198f' : '#1e40af',
                    fontWeight: 700,
                  }}
                />
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a', mb: 0.5 }}>
                {election.nombre}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {election.school?.nombre || 'Colegio Registrado'} • RBD: {election.school?.rbd || 'S/N'} • Comuna: {election.school?.comuna || 'Santiago'}
              </Typography>
            </Box>

            {/* Botones de Acción de Estado y Actas PDF */}
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
              {election.estado === 'Borrador' && (
                <Button
                  variant="contained"
                  color="success"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleOpenElection}
                  sx={{ fontWeight: 700 }}
                >
                  Abrir Elección
                </Button>
              )}

              {election.estado === 'Abierta' && (
                <>
                  <Button
                    variant="contained"
                    color="warning"
                    startIcon={<LockIcon />}
                    onClick={handleCloseElection}
                    sx={{ fontWeight: 700 }}
                  >
                    Cerrar Elección
                  </Button>
                  <Button
                    component={Link}
                    to="/votar"
                    target="_blank"
                    variant="contained"
                    sx={{ backgroundColor: '#2563eb', fontWeight: 700 }}
                    startIcon={<HowToVoteIcon />}
                  >
                    Ir a Sala de Votación
                  </Button>
                </>
              )}

              {/* Botón Descargar Acta de Apertura */}
              <Button
                onClick={handleDownloadActaApertura}
                variant="outlined"
                startIcon={<PictureAsPdfIcon />}
                sx={{ borderColor: '#cbd5e1', color: '#0d233a', fontWeight: 600 }}
              >
                Acta Apertura (PDF)
              </Button>

              {/* Botón Descargar Acta de Cierre (solo disponible tras el cierre) */}
              {(election.estado === 'Cerrada' || election.estado === 'Finalizada') && (
                <Button
                  onClick={handleDownloadActaCierre}
                  variant="outlined"
                  color="secondary"
                  startIcon={<PictureAsPdfIcon />}
                  sx={{ fontWeight: 600 }}
                >
                  Acta Cierre (PDF)
                </Button>
              )}
            </Box>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 900 }}>
            {election.descripcion || 'Sin descripción ingresada.'}
          </Typography>
        </CardContent>

        <Divider />

        {/* Pestañas de Gestión */}
        <Tabs
          value={tabIndex}
          onChange={(e, val) => setTabIndex(val)}
          sx={{
            px: 2,
            backgroundColor: '#f8fafc',
            '& .MuiTab-root': { fontWeight: 700, py: 2, textTransform: 'none' },
          }}
        >
          <Tab label={`Padrón Electoral (${voters.length})`} />
          <Tab label={`Candidatos y Listas (${candidates.length})`} />
          <Tab label="Generador de Credenciales y Correo" />
          <Tab label="Escrutinio y Resultados Oficiales" />
          <Tab label={`Comisión Electoral (${election.committee_members?.length || 0})`} />
        </Tabs>
      </Card>

      {/* ========================================================================= */}
      {/* TAB 0: PADRÓN ELECTORAL (Módulo 2)                                        */}
      {/* ========================================================================= */}
      {tabIndex === 0 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a' }}>
                Padrón de Electores Habilitados
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Validación de RUT chileno con Módulo 11, verificación de correos y regla por familia
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1.5 }}>
              <Button
                component="a"
                href={voterService.getTemplateDownloadUrl(election.id)}
                startIcon={<DownloadIcon />}
                variant="outlined"
                size="small"
              >
                Plantilla Excel
              </Button>
              <Button
                variant="outlined"
                color="primary"
                startIcon={<UploadFileIcon />}
                onClick={() => setOpenUploadModal(true)}
              >
                Subir Padrón Excel / CSV
              </Button>
              <Button
                variant="contained"
                startIcon={<PersonAddIcon />}
                sx={{ backgroundColor: '#0d233a' }}
                onClick={() => setOpenAddVoterModal(true)}
              >
                Agregar Elector
              </Button>
            </Box>
          </Box>

          {/* Buscador de Electores */}
          <Card sx={{ mb: 3, borderRadius: 2 }}>
            <CardContent sx={{ p: 2 }}>
              <TextField
                fullWidth
                size="small"
                placeholder="Buscar por RUT, Nombre, Curso o Token..."
                value={voterSearch}
                onChange={(e) => setVoterSearch(e.target.value)}
              />
            </CardContent>
          </Card>

          {/* Tabla de Votantes */}
          <TableContainer component={Paper} sx={{ borderRadius: 2, border: '1px solid #e2e8f0' }}>
            <Table>
              <TableHead sx={{ backgroundColor: '#f8fafc' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>#</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>RUT</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Nombre Completo</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Curso</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Correo</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Familia ID</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Estado</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Token Asignado</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredVoters.map((v, i) => (
                  <TableRow key={v.id} hover>
                    <TableCell>{i + 1}</TableCell>
                    <TableCell sx={{ fontWeight: 600 }}>{v.rut}</TableCell>
                    <TableCell>{v.nombre}</TableCell>
                    <TableCell>{v.curso || '-'}</TableCell>
                    <TableCell>{v.correo || '-'}</TableCell>
                    <TableCell>
                      {v.familia_id ? (
                        <Chip label={v.familia_id} size="small" sx={{ fontWeight: 600, backgroundColor: '#f3e8ff', color: '#6b21a8' }} />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={v.estado} />
                    </TableCell>
                    <TableCell>
                      {v.token_votacion ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <code style={{ fontSize: '0.8rem', background: '#f1f5f9', padding: '2px 6px', borderRadius: 4 }}>
                            {v.token_votacion.substring(0, 13)}...
                          </code>
                          <Tooltip title="Copiar Token">
                            <IconButton size="small" onClick={() => copyToClipboard(v.token_votacion, 'Token copiado')}>
                              <ContentCopyIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      ) : (
                        <Chip label="Sin Token" size="small" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: CANDIDATOS Y LISTAS (Módulo 1/7)                                   */}
      {/* ========================================================================= */}
      {tabIndex === 1 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a' }}>
                Opciones y Listas Postulantes
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Candidatos habilitados para sufragio (incluye voto en blanco y voto nulo institucional)
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<PersonAddIcon />}
              sx={{ backgroundColor: '#0d233a' }}
              onClick={() => setOpenAddCandidateModal(true)}
            >
              Agregar Candidato / Lista
            </Button>
          </Box>

          <Grid container spacing={3}>
            {candidates.map((c) => (
              <Grid item xs={12} sm={6} md={4} key={c.id}>
                <Card
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: 3,
                    border: c.es_blanco || c.es_nulo ? '1px dashed #cbd5e1' : '1px solid #e2e8f0',
                    backgroundColor: c.es_blanco || c.es_nulo ? '#f8fafc' : '#ffffff',
                  }}
                >
                  {c.foto && (
                    <Box
                      component="img"
                      src={c.foto}
                      alt={c.nombre}
                      sx={{ height: 160, width: '100%', objectFit: 'cover', borderTopLeftRadius: 12, borderTopRightRadius: 12 }}
                    />
                  )}
                  <CardContent sx={{ p: 2.5, flexGrow: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                      <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                        {c.nombre}
                      </Typography>
                      {!(c.es_blanco || c.es_nulo) && (
                        <IconButton size="small" color="error" onClick={() => handleDeleteCandidate(c.id)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      )}
                    </Box>

                    {c.cargo && (
                      <Typography variant="subtitle2" sx={{ color: '#1e40af', fontWeight: 600, mb: 1.5 }}>
                        {c.cargo}
                      </Typography>
                    )}

                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {c.descripcion}
                    </Typography>

                    <Divider sx={{ my: 1.5 }} />

                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#64748b' }}>
                        Sufragios Obtenidos:
                      </Typography>
                      <Chip
                        label={`${c.votos_count || 0} votos`}
                        size="small"
                        color={c.votos_count > 0 ? 'success' : 'default'}
                        sx={{ fontWeight: 700 }}
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: GENERADOR DE CREDENCIALES Y CORREO (Módulo 4)                       */}
      {/* ========================================================================= */}
      {tabIndex === 2 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a' }}>
                Generación y Despacho de Credenciales (Módulo 4)
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Emisión de tokens criptográficos UUID v4 y simulación de envío a casillas de correo
              </Typography>
            </Box>
            <Button
              variant="contained"
              color="primary"
              startIcon={<EmailIcon />}
              onClick={handleSimulateEmails}
              sx={{ fontWeight: 700 }}
            >
              Simular Envío Masivo de Correos
            </Button>
          </Box>

          <Alert severity="info" sx={{ mb: 3, borderRadius: 2 }}>
            <strong>Protección de Credenciales:</strong> Por estrictos principios de secreto electoral y confidencialidad, las credenciales de votación son privadas de cada elector y no se exponen en las vistas de administración. Los electores ingresan directamente a la{' '}
            <Link to="/votar" target="_blank" style={{ color: '#1e40af', fontWeight: 'bold', textDecoration: 'underline' }}>
              Sala de Votación (/votar)
            </Link>{' '}
            con su credencial personal enviada por canal seguro.
          </Alert>

          <TableContainer component={Paper} sx={{ borderRadius: 2, border: '1px solid #e2e8f0' }}>
            <Table>
              <TableHead sx={{ backgroundColor: '#f8fafc' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700 }}>Elector</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>RUT</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Curso</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Correo Destino</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Familia ID</TableCell>
                  <TableCell sx={{ fontWeight: 700 }}>Estado</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredVoters.map((v) => (
                  <TableRow key={v.id} hover>
                    <TableCell sx={{ fontWeight: 600 }}>{v.nombre}</TableCell>
                    <TableCell>{v.rut}</TableCell>
                    <TableCell>{v.curso || '-'}</TableCell>
                    <TableCell>{v.correo || 'sin_correo@demo.cl'}</TableCell>
                    <TableCell>
                      {v.familia_id ? (
                        <Chip label={v.familia_id} size="small" variant="outlined" />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={v.estado} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: ESCRUTINIO Y RESULTADOS OFICIALES (Módulo 7 & 8)                    */}
      {/* ========================================================================= */}
      {tabIndex === 3 && (
        <Box>
          {election.estado !== 'Cerrada' && election.estado !== 'Finalizada' ? (
            <Card sx={{ p: 5, textAlign: 'center', borderRadius: 3, border: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
              <LockIcon sx={{ fontSize: 56, color: '#64748b', mb: 2 }} />
              <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a', mb: 1 }}>
                Escrutinio Protegido por Secreto Electoral
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 650, mx: 'auto', mb: 3 }}>
                El escrutinio detallado, conteo de votos por candidatura y acta definitiva se encuentran
                estrictamente protegidos mientras el proceso electoral permanezca en estado <strong>{election.estado}</strong>.
                Estarán disponibles automáticamente una vez que la elección sea formalmente cerrada.
              </Typography>
              <Chip
                label={`Estado del Proceso: ${election.estado}`}
                color={election.estado === 'Abierta' ? 'success' : 'default'}
                sx={{ fontWeight: 700, px: 2, py: 1 }}
              />
            </Card>
          ) : scrutiny ? (
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a' }}>
                    Escrutinio Oficial y Resultados (Módulo 7)
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Cómputo oficial de sufragios, cálculo de porcentajes y proclamación de resultados
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 1.5 }}>
                  <Button
                    onClick={handleDownloadActaCierre}
                    variant="contained"
                    color="primary"
                    startIcon={<PictureAsPdfIcon />}
                    sx={{ fontWeight: 700 }}
                  >
                    Descargar Acta de Cierre Oficial (PDF)
                  </Button>
                </Box>
              </Box>

          {/* Banner de Proclamación de Ganador */}
          {scrutiny.ganador ? (
            <Card
              sx={{
                mb: 4,
                backgroundColor: '#ecfdf5',
                border: '2px solid #059669',
                borderRadius: 3,
                p: 1,
              }}
            >
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 3, p: 2 }}>
                <Box
                  sx={{
                    width: 60,
                    height: 60,
                    borderRadius: '50%',
                    backgroundColor: '#10b981',
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.4)',
                  }}
                >
                  <EmojiEventsIcon sx={{ fontSize: 36 }} />
                </Box>
                <Box>
                  <Typography variant="caption" sx={{ fontWeight: 800, color: '#047857', letterSpacing: '0.05em' }}>
                    OPCIÓN ELECTA / GANADORA DE LA ELECCIÓN
                  </Typography>
                  <Typography variant="h4" sx={{ fontWeight: 800, color: '#064e3b' }}>
                    {scrutiny.ganador.nombre}
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#065f46', fontWeight: 600 }}>
                    {scrutiny.ganador.cargo || 'Directiva Electa'} • {scrutiny.ganador.votos} votos obtenidos ({scrutiny.ganador.porcentaje}%)
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ) : (
            <Alert severity="info" sx={{ mb: 4, borderRadius: 2 }}>
              Aún no se registran sufragios con ventaja o la elección no ha sido cerrada formalmente.
            </Alert>
          )}

          {/* Tarjetas de Métricas de Escrutinio */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2.5, borderRadius: 2, border: '1px solid #e2e8f0', textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 600 }}>
                  Padrón Habilitado
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a', my: 0.5 }}>
                  {scrutiny.total_padron}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Electores registrados
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2.5, borderRadius: 2, border: '1px solid #a7f3d0', backgroundColor: '#f0fdf4', textAlign: 'center' }}>
                <Typography variant="body2" sx={{ color: '#047857', fontWeight: 600 }}>
                  Votos Emitidos
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: '#065f46', my: 0.5 }}>
                  {scrutiny.total_votos}
                </Typography>
                <Typography variant="caption" sx={{ color: '#047857' }}>
                  Sufragios válidamente recibidos
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2.5, borderRadius: 2, border: '1px solid #bfdbfe', backgroundColor: '#eff6ff', textAlign: 'center' }}>
                <Typography variant="body2" sx={{ color: '#1e40af', fontWeight: 600 }}>
                  Participación
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: '#1e3a8a', my: 0.5 }}>
                  {scrutiny.participacion_porcentaje}%
                </Typography>
                <Typography variant="caption" sx={{ color: '#1e40af' }}>
                  Porcentaje total del padrón
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Paper sx={{ p: 2.5, borderRadius: 2, border: '1px solid #fed7aa', backgroundColor: '#fff7ed', textAlign: 'center' }}>
                <Typography variant="body2" sx={{ color: '#9a3412', fontWeight: 600 }}>
                  Votos Pendientes
                </Typography>
                <Typography variant="h4" sx={{ fontWeight: 800, color: '#7c2d12', my: 0.5 }}>
                  {scrutiny.votos_pendientes}
                </Typography>
                <Typography variant="caption" sx={{ color: '#9a3412' }}>
                  Por emitir sufragio
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* Tabla Desglosada de Resultados */}
          <Card sx={{ borderRadius: 2, mb: 4 }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a', mb: 2 }}>
                Desglose Detallado por Candidato y Opción
              </Typography>
              <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0' }}>
                <Table>
                  <TableHead sx={{ backgroundColor: '#f8fafc' }}>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700 }}>Opción Postulante</TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>Cargo / Postulación</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 700 }}>Total Votos</TableCell>
                      <TableCell sx={{ fontWeight: 700, width: '35%' }}>Porcentaje y Barra Visual</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {scrutiny.candidatos.map((cand) => (
                      <TableRow key={cand.candidate_id} hover>
                        <TableCell>
                          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0d233a' }}>
                            {cand.nombre}
                          </Typography>
                        </TableCell>
                        <TableCell>{cand.cargo || '-'}</TableCell>
                        <TableCell align="center">
                          <Chip
                            label={`${cand.votos} votos`}
                            size="small"
                            color={cand.votos > 0 ? 'primary' : 'default'}
                            sx={{ fontWeight: 700 }}
                          />
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Box sx={{ flexGrow: 1 }}>
                              <LinearProgress
                                variant="determinate"
                                value={cand.porcentaje}
                                sx={{
                                  height: 8,
                                  borderRadius: 4,
                                  backgroundColor: '#e2e8f0',
                                  '& .MuiLinearProgress-bar': {
                                    backgroundColor: cand.es_blanco || cand.es_nulo ? '#94a3b8' : '#1e40af',
                                  },
                                }}
                              />
                            </Box>
                            <Typography variant="body2" sx={{ fontWeight: 700, minWidth: 45 }}>
                              {cand.porcentaje}%
                            </Typography>
                          </Box>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>
      ) : null}
    </Box>
  )}

      {/* ========================================================================= */}
      {/* TAB 4: COMISIÓN ELECTORAL                                                 */}
      {/* ========================================================================= */}
      {tabIndex === 4 && (
        <Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, color: '#0d233a' }}>
                Comisión Electoral Supervisora
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Ministros de fe acreditados que firman las actas oficiales de apertura y cierre
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<PersonAddIcon />}
              sx={{ backgroundColor: '#0d233a' }}
              onClick={() => setOpenAddCommitteeModal(true)}
            >
              Agregar Miembro
            </Button>
          </Box>

          <Grid container spacing={3}>
            {election.committee_members?.map((m) => (
              <Grid item xs={12} sm={6} md={4} key={m.id}>
                <Card sx={{ borderRadius: 3, border: '1px solid #e2e8f0' }}>
                  <CardContent sx={{ p: 2.5 }}>
                    <Chip label={m.cargo} size="small" color="primary" sx={{ fontWeight: 700, mb: 1.5 }} />
                    <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                      {m.nombre}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      RUT: {m.rut}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      Correo: {m.correo || '-'}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* ========================================================================= */}
      {/* MODAL: SUBIR PADRÓN EXCEL / CSV (Módulo 2)                                */}
      {/* ========================================================================= */}
      <Dialog open={openUploadModal} onClose={() => setOpenUploadModal(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>
          Carga Masiva de Padrón Electoral (Excel / CSV)
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Suba un archivo con columnas: <strong>RUT, Nombre, Curso, Correo, Familia ID</strong>. El sistema validará matemáticamente cada RUT (Módulo 11), verificará correos y evitará duplicados.
          </Typography>

          <Box sx={{ mb: 3 }}>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => setUploadFile(e.target.files[0])}
              style={{ display: 'block', width: '100%', padding: '10px', border: '1px dashed #94a3b8', borderRadius: 8 }}
            />
          </Box>

          {uploadLoading && <LinearProgress sx={{ my: 2 }} />}

          {/* Resultado de la Carga */}
          {uploadResult && (
            <Box sx={{ mt: 2 }}>
              <Alert severity={uploadResult.total_errores > 0 ? 'warning' : 'success'} sx={{ mb: 2 }}>
                Se procesaron <strong>{uploadResult.total_leidos}</strong> filas:{' '}
                <strong>{uploadResult.insertados}</strong> electores agregados con éxito.{' '}
                {uploadResult.total_errores > 0 && `${uploadResult.total_errores} filas presentaron errores.`}
              </Alert>

              {uploadResult.errores?.length > 0 && (
                <Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#b91c1c', mb: 1 }}>
                    Detalle de Errores Encontrados:
                  </Typography>
                  <Paper variant="outlined" sx={{ maxHeight: 200, overflow: 'auto', p: 1, backgroundColor: '#fef2f2' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>Fila</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>RUT</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>Motivo del Error</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {uploadResult.errores.map((err, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{err.fila}</TableCell>
                            <TableCell>{err.rut}</TableCell>
                            <TableCell sx={{ color: '#dc2626' }}>{err.motivo}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Paper>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setOpenUploadModal(false)}>Cerrar</Button>
          <Button variant="contained" onClick={handleUploadSubmit} disabled={!uploadFile || uploadLoading}>
            Procesar y Cargar
          </Button>
        </DialogActions>
      </Dialog>

      {/* ========================================================================= */}
      {/* MODAL: AGREGAR ELECTOR INDIVIDUAL                                         */}
      {/* ========================================================================= */}
      <Dialog open={openAddVoterModal} onClose={() => setOpenAddVoterModal(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleCreateVoter}>
          <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>Agregar Elector al Padrón</DialogTitle>
          <DialogContent dividers>
            <TextField
              fullWidth
              label="RUT Chileno"
              placeholder="ej: 12.345.678-9"
              value={newVoter.rut}
              onChange={(e) => setNewVoter({ ...newVoter, rut: e.target.value })}
              required
              helperText="El sistema verifica el dígito verificador Módulo 11"
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Nombre Completo"
              value={newVoter.nombre}
              onChange={(e) => setNewVoter({ ...newVoter, nombre: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Curso o Grado"
              placeholder="ej: 3° Básico A"
              value={newVoter.curso}
              onChange={(e) => setNewVoter({ ...newVoter, curso: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              type="email"
              label="Correo Electrónico"
              value={newVoter.correo}
              onChange={(e) => setNewVoter({ ...newVoter, correo: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Familia ID (Opcional para regla de familia)"
              placeholder="ej: FAM-101"
              value={newVoter.familia_id}
              onChange={(e) => setNewVoter({ ...newVoter, familia_id: e.target.value })}
              helperText="Si la regla es 'Un voto por familia', miembros con el mismo ID comparten el voto."
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenAddVoterModal(false)}>Cancelar</Button>
            <Button type="submit" variant="contained">Guardar Elector</Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* ========================================================================= */}
      {/* MODAL: AGREGAR CANDIDATO                                                  */}
      {/* ========================================================================= */}
      <Dialog open={openAddCandidateModal} onClose={() => setOpenAddCandidateModal(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleCreateCandidate}>
          <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>Agregar Candidato o Lista</DialogTitle>
          <DialogContent dividers>
            <TextField
              fullWidth
              label="Nombre de la Lista o Candidato"
              placeholder="ej: Lista D: Futuro Sustentable"
              value={newCandidate.nombre}
              onChange={(e) => setNewCandidate({ ...newCandidate, nombre: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Cargo o Representante"
              placeholder="ej: Presidencia: Roberto Gómez"
              value={newCandidate.cargo}
              onChange={(e) => setNewCandidate({ ...newCandidate, cargo: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Propuesta y Descripción"
              value={newCandidate.descripcion}
              onChange={(e) => setNewCandidate({ ...newCandidate, descripcion: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="URL de Foto (Opcional)"
              placeholder="https://..."
              value={newCandidate.foto}
              onChange={(e) => setNewCandidate({ ...newCandidate, foto: e.target.value })}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenAddCandidateModal(false)}>Cancelar</Button>
            <Button type="submit" variant="contained">Guardar Opción</Button>
          </DialogActions>
        </form>
      </Dialog>

      {/* ========================================================================= */}
      {/* MODAL: SIMULACIÓN DE CORREOS (Módulo 4)                                   */}
      {/* ========================================================================= */}
      <Dialog open={openEmailModal} onClose={() => setOpenEmailModal(false)} maxWidth="md" fullWidth>
        <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>
          Simulador de Despacho de Credenciales por Correo
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Vista previa de los correos electrónicos generados con plantillas HTML y enlaces directos de sufragio para los electores.
          </Typography>

          {emailSimulationData?.correos_simulados?.slice(0, 3).map((item, idx) => (
            <Card key={idx} sx={{ mb: 3, border: '1px solid #cbd5e1' }}>
              <Box sx={{ p: 1.5, backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                  Destinatario: {item.nombre} &lt;{item.correo}&gt;
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => copyToClipboard(item.token, 'Token copiado')}
                >
                  Copiar Token
                </Button>
              </Box>
              <Box sx={{ p: 2 }} dangerouslySetInnerHTML={{ __html: item.preview_html }} />
            </Card>
          ))}
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setOpenEmailModal(false)}>Cerrar Simulador</Button>
        </DialogActions>
      </Dialog>

      {/* ========================================================================= */}
      {/* MODAL: AGREGAR COMISIÓN                                                   */}
      {/* ========================================================================= */}
      <Dialog open={openAddCommitteeModal} onClose={() => setOpenAddCommitteeModal(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleAddCommittee}>
          <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>Agregar Miembro a Comisión Electoral</DialogTitle>
          <DialogContent dividers>
            <TextField
              fullWidth
              label="Nombre Completo"
              value={newCommittee.nombre}
              onChange={(e) => setNewCommittee({ ...newCommittee, nombre: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="RUT"
              value={newCommittee.rut}
              onChange={(e) => setNewCommittee({ ...newCommittee, rut: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Cargo"
              value={newCommittee.cargo}
              onChange={(e) => setNewCommittee({ ...newCommittee, cargo: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              type="email"
              label="Correo Electrónico"
              value={newCommittee.correo}
              onChange={(e) => setNewCommittee({ ...newCommittee, correo: e.target.value })}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenAddCommitteeModal(false)}>Cancelar</Button>
            <Button type="submit" variant="contained">Guardar Miembro</Button>
          </DialogActions>
        </form>
      </Dialog>
    </Container>
  );
};

export default ElectionDetail;
