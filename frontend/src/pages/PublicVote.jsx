import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Alert,
  Grid,
  Radio,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Paper,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import { useSearchParams, Link } from 'react-router-dom';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import VerifiedUserIcon from '@mui/icons-material/VerifiedUser';
import LockIcon from '@mui/icons-material/Lock';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import SchoolIcon from '@mui/icons-material/School';
import confetti from 'canvas-confetti';

import { votingService } from '../services/api';
import TheoGenLogo from '../components/TheoGenLogo';

const PublicVote = () => {
  const [searchParams] = useSearchParams();
  const initialToken = searchParams.get('token') || '';

  const [tokenInput, setTokenInput] = useState(initialToken);
  const [tokenData, setTokenData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Selección de candidato
  const [selectedCandidateId, setSelectedCandidateId] = useState(null);
  const [openConfirmModal, setOpenConfirmModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Recibo de voto emitido
  const [voteReceipt, setVoteReceipt] = useState(null);
  const [copiedHash, setCopiedHash] = useState(false);

  useEffect(() => {
    if (initialToken) {
      handleValidateToken(initialToken);
      // Sanitizar la barra de direcciones del navegador inmediatamente para no exponer el token en historial/URL
      if (typeof window !== 'undefined' && window.history && window.history.replaceState) {
        window.history.replaceState({}, document.title, window.location.pathname);
      }
    }
  }, [initialToken]);

  const handleValidateToken = async (tokenToTest) => {
    const clean = (tokenToTest || tokenInput).trim();
    if (!clean) {
      setErrorMsg('Por favor ingrese su token único de votación.');
      return;
    }

    setLoading(true);
    setErrorMsg('');
    setTokenData(null);
    setSelectedCandidateId(null);
    setVoteReceipt(null);

    try {
      const res = await votingService.validateToken(clean);
      if (!res.valido) {
        setErrorMsg(res.mensaje);
      } else {
        setTokenData(res);
      }
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Error al validar el token de votación.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenConfirm = () => {
    if (!selectedCandidateId) {
      setErrorMsg('Debe seleccionar una de las opciones para emitir su sufragio.');
      return;
    }
    setOpenConfirmModal(true);
  };

  const handleConfirmVote = async () => {
    setSubmitting(true);
    setOpenConfirmModal(false);
    try {
      const res = await votingService.submitVote(tokenInput.trim(), selectedCandidateId);
      setVoteReceipt(res);

      // Lanzar confeti de celebración
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 },
      });
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Error al registrar su voto.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleCopyHash = () => {
    if (voteReceipt?.hash_integridad) {
      navigator.clipboard.writeText(voteReceipt.hash_integridad);
      setCopiedHash(true);
      setTimeout(() => setCopiedHash(false), 3000);
    }
  };

  const handleResetForAnotherVote = () => {
    setTokenInput('');
    setTokenData(null);
    setSelectedCandidateId(null);
    setVoteReceipt(null);
    setErrorMsg('');
  };

  const selectedCandidate = tokenData?.candidatos?.find((c) => c.id === selectedCandidateId);

  return (
    <Box sx={{ minHeight: 'calc(100vh - 70px)', py: 5, backgroundColor: '#f8fafc' }}>
      <Container maxWidth="md">
        {/* Encabezado Institucional TheoGen */}
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Box sx={{ display: 'inline-flex', mb: 1 }}>
            <TheoGenLogo />
          </Box>
          <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a', mb: 0.5 }}>
            Sala de Votación Digital
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Proceso de sufragio electrónico confidencial, auditable e irreversible
          </Typography>
        </Box>

        {/* ===================================================================== */}
        {/* PASO 3: PANTALLA DE COMPROBANTE FINAL EXITOSO                          */}
        {/* ===================================================================== */}
        {voteReceipt ? (
          <Card
            sx={{
              borderRadius: 4,
              boxShadow: '0 15px 35px -5px rgba(5, 150, 105, 0.15)',
              border: '2px solid #a7f3d0',
              overflow: 'hidden',
            }}
          >
            <Box sx={{ backgroundColor: '#ecfdf5', p: 4, textAlign: 'center', borderBottom: '1px solid #a7f3d0' }}>
              <Box
                sx={{
                  width: 72,
                  height: 72,
                  borderRadius: '50%',
                  backgroundColor: '#10b981',
                  color: '#ffffff',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  mb: 2,
                  boxShadow: '0 6px 16px rgba(16, 185, 129, 0.4)',
                }}
              >
                <CheckCircleIcon sx={{ fontSize: 44 }} />
              </Box>
              <Typography variant="h4" sx={{ fontWeight: 800, color: '#064e3b', mb: 1 }}>
                ¡Sufragio Registrado Exitosamente!
              </Typography>
              <Typography variant="body1" sx={{ color: '#047857', fontWeight: 600 }}>
                Tu voto fue sellado y depositado de forma segura en la urna digital.
              </Typography>
            </Box>

            <CardContent sx={{ p: 4 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#475569', mb: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Comprobante Digital de Participación
              </Typography>

              <Paper variant="outlined" sx={{ p: 2.5, mb: 3, backgroundColor: '#f8fafc', borderRadius: 2 }}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">
                      Proceso Eleccionario:
                    </Typography>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0d233a' }}>
                      {voteReceipt.eleccion_nombre}
                    </Typography>
                  </Grid>

                  <Grid item xs={12} sm={6}>
                    <Typography variant="caption" color="text.secondary">
                      Institución:
                    </Typography>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0d233a' }}>
                      {voteReceipt.colegio_nombre}
                    </Typography>
                  </Grid>

                  <Grid item xs={12}>
                    <Divider sx={{ my: 1 }} />
                  </Grid>

                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary">
                      Hash Criptográfico de Integridad (SHA-256):
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      <code
                        style={{
                          wordBreak: 'break-all',
                          fontSize: '0.85rem',
                          backgroundColor: '#e2e8f0',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontWeight: 700,
                          color: '#0f172a',
                          flexGrow: 1,
                        }}
                      >
                        {voteReceipt.hash_integridad}
                      </code>
                      <Tooltip title={copiedHash ? '¡Copiado!' : 'Copiar Hash'}>
                        <IconButton onClick={handleCopyHash} color="primary" sx={{ backgroundColor: '#eff6ff' }}>
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                    <Typography variant="caption" sx={{ color: '#64748b', display: 'block', mt: 1 }}>
                      Este identificador único garantiza que su voto fue contabilizado en la urna sin vincularlo públicamente a su identidad.
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap' }}>
                <Button
                  variant="outlined"
                  onClick={handleResetForAnotherVote}
                  startIcon={<HowToVoteIcon />}
                  sx={{ fontWeight: 700 }}
                >
                  Probar con Otro Token Demo
                </Button>
                <Button
                  component={Link}
                  to="/"
                  variant="contained"
                  sx={{ backgroundColor: '#0d233a', fontWeight: 700 }}
                >
                  Volver al Panel General
                </Button>
              </Box>
            </CardContent>
          </Card>
        ) : !tokenData ? (
          /* ===================================================================== */
          /* PASO 1: INGRESO DE CREDENCIALES (TOKEN)                                */
          /* ===================================================================== */
          <Card sx={{ p: 2, borderRadius: 3, boxShadow: '0 8px 30px rgba(13, 35, 58, 0.08)' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2 }}>
                <LockIcon sx={{ color: '#1e40af' }} />
                <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                  Ingrese su Token Único de Votación
                </Typography>
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                El token UUID es su credencial digital intransferible enviada por la Comisión Electoral a su correo.
              </Typography>

              {errorMsg && (
                <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
                  {errorMsg}
                </Alert>
              )}

              <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: { xs: 'wrap', sm: 'nowrap' } }}>
                <TextField
                  fullWidth
                  placeholder="3a8f803d-0ccb-48b7-89f7-d92aa4c729de"
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleValidateToken()}
                  autoFocus
                />
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => handleValidateToken()}
                  disabled={loading || !tokenInput.trim()}
                  startIcon={<VerifiedUserIcon />}
                  sx={{
                    px: 3,
                    fontWeight: 700,
                    minWidth: 160,
                    backgroundColor: '#0d233a',
                    '&:hover': { backgroundColor: '#1e40af' },
                  }}
                >
                  {loading ? 'Validando...' : 'Ingresar'}
                </Button>
              </Box>

              {loading && <LinearProgress sx={{ mb: 3 }} />}

              {/* Botones de Prueba Rápida para el Evaluador */}
              <Divider sx={{ my: 3 }}>
                <Typography variant="caption" sx={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Tokens de Prueba Demo Incluidos
                </Typography>
              </Divider>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      cursor: 'pointer',
                      borderRadius: 2,
                      backgroundColor: '#f8fafc',
                      '&:hover': { borderColor: '#1e40af', backgroundColor: '#eff6ff' },
                    }}
                    onClick={() => {
                      setTokenInput('3a8f803d-0ccb-48b7-89f7-d92aa4c729de');
                      handleValidateToken('3a8f803d-0ccb-48b7-89f7-d92aa4c729de');
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#1e40af' }}>
                      Token Demo 1 (Francisca Silva)
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Familia: FAM-101 • 1° Básico A
                    </Typography>
                    <code style={{ display: 'block', fontSize: '0.72rem', color: '#64748b', marginTop: 4 }}>
                      3a8f803d-0ccb-48b7-89f7-d92aa4c729de
                    </code>
                  </Paper>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      cursor: 'pointer',
                      borderRadius: 2,
                      backgroundColor: '#f8fafc',
                      '&:hover': { borderColor: '#1e40af', backgroundColor: '#eff6ff' },
                    }}
                    onClick={() => {
                      setTokenInput('b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e');
                      handleValidateToken('b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e');
                    }}
                  >
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#1e40af' }}>
                      Token Demo 2 (Rodrigo Silva)
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Misma familia FAM-101 (Para probar bloqueo familiar)
                    </Typography>
                    <code style={{ display: 'block', fontSize: '0.72rem', color: '#64748b', marginTop: 4 }}>
                      b1c2d3e4-5f6a-7b8c-9d0e-1f2a3b4c5d6e
                    </code>
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        ) : (
          /* ===================================================================== */
          /* PASO 2: SELECCIÓN DE CANDIDATO Y SUFRAGIO                              */
          /* ===================================================================== */
          <Box>
            {/* Banner de Validación Exitosa */}
            <Paper
              elevation={0}
              sx={{
                p: 2.5,
                mb: 3,
                backgroundColor: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: 3,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 2,
              }}
            >
              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <SchoolIcon sx={{ color: '#1e40af', fontSize: 20 }} />
                  <Typography variant="caption" sx={{ fontWeight: 700, color: '#1e40af', textTransform: 'uppercase' }}>
                    {tokenData.colegio_nombre} • {tokenData.eleccion_tipo}
                  </Typography>
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 800, color: '#0d233a' }}>
                  {tokenData.eleccion_nombre}
                </Typography>
                <Typography variant="body2" sx={{ color: '#1e3a8a', fontWeight: 600, mt: 0.5 }}>
                  Elector Habilitado: <strong>{tokenData.elector_nombre}</strong> • Regla: {tokenData.regla_votacion}
                </Typography>
              </Box>

              <Button size="small" variant="outlined" onClick={handleResetForAnotherVote}>
                Cambiar Token
              </Button>
            </Paper>

            {errorMsg && (
              <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
                {errorMsg}
              </Alert>
            )}

            <Typography variant="h5" sx={{ fontWeight: 800, color: '#0d233a', mb: 1 }}>
              Seleccione su Preferencia
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Haga clic sobre la tarjeta de su candidato, lista o voto institucional para marcar su opción.
            </Typography>

            {/* Listado de Opciones de Votación */}
            <Grid container spacing={2.5} sx={{ mb: 4 }}>
              {tokenData.candidatos?.map((cand) => {
                const isSelected = selectedCandidateId === cand.id;
                const isInstitutional = cand.es_blanco || cand.es_nulo;

                return (
                  <Grid item xs={12} key={cand.id}>
                    <Paper
                      elevation={isSelected ? 4 : 0}
                      onClick={() => setSelectedCandidateId(cand.id)}
                      sx={{
                        p: 2.5,
                        borderRadius: 3,
                        cursor: 'pointer',
                        border: isSelected ? '2px solid #1e40af' : '1px solid #e2e8f0',
                        backgroundColor: isSelected ? '#eff6ff' : isInstitutional ? '#fafbfc' : '#ffffff',
                        transition: 'all 0.2s ease',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 2,
                        '&:hover': {
                          borderColor: isSelected ? '#1e40af' : '#94a3b8',
                          boxShadow: '0 4px 14px rgba(0,0,0,0.06)',
                        },
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                        <Radio
                          checked={isSelected}
                          onChange={() => setSelectedCandidateId(cand.id)}
                          value={cand.id}
                        />

                        {cand.foto && (
                          <Box
                            component="img"
                            src={cand.foto}
                            alt={cand.nombre}
                            sx={{ width: 60, height: 60, borderRadius: '50%', objectFit: 'cover' }}
                          />
                        )}

                        <Box>
                          <Typography variant="h6" sx={{ fontWeight: 800, color: '#0d233a', lineHeight: 1.2 }}>
                            {cand.nombre}
                          </Typography>
                          {cand.cargo && (
                            <Typography variant="body2" sx={{ color: '#1e40af', fontWeight: 600, mt: 0.3 }}>
                              {cand.cargo}
                            </Typography>
                          )}
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                            {cand.descripcion}
                          </Typography>
                        </Box>
                      </Box>

                      {isSelected && (
                        <Chip
                          label="Opción Seleccionada"
                          color="primary"
                          size="small"
                          sx={{ fontWeight: 700 }}
                        />
                      )}
                    </Paper>
                  </Grid>
                );
              })}
            </Grid>

            {/* Botón de Emisión */}
            <Box sx={{ textAlign: 'center' }}>
              <Button
                variant="contained"
                size="large"
                disabled={!selectedCandidateId || submitting}
                onClick={handleOpenConfirm}
                startIcon={<HowToVoteIcon />}
                sx={{
                  py: 1.8,
                  px: 6,
                  fontSize: '1.15rem',
                  fontWeight: 800,
                  backgroundColor: '#0d233a',
                  borderRadius: 3,
                  boxShadow: '0 6px 20px rgba(13, 35, 58, 0.3)',
                  '&:hover': { backgroundColor: '#1e40af' },
                }}
              >
                {submitting ? 'Sellando Voto...' : 'Continuar y Confirmar Voto'}
              </Button>
            </Box>
          </Box>
        )}

        {/* Modal de Confirmación Definitiva */}
        <Dialog open={openConfirmModal} onClose={() => setOpenConfirmModal(false)} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ fontWeight: 800, color: '#0d233a', display: 'flex', alignItems: 'center', gap: 1 }}>
            <WarningAmberIcon color="warning" /> Confirmar Emisión de Sufragio
          </DialogTitle>
          <DialogContent dividers>
            <Typography variant="body1" sx={{ mb: 2 }}>
              Ha seleccionado la siguiente opción:
            </Typography>
            <Paper variant="outlined" sx={{ p: 2, backgroundColor: '#f8fafc', borderRadius: 2, mb: 2, textAlign: 'center' }}>
              <Typography variant="h6" sx={{ fontWeight: 800, color: '#0d233a' }}>
                {selectedCandidate?.nombre}
              </Typography>
              {selectedCandidate?.cargo && (
                <Typography variant="caption" color="text.secondary">
                  {selectedCandidate.cargo}
                </Typography>
              )}
            </Paper>
            <Alert severity="warning" sx={{ borderRadius: 2 }}>
              <strong>Advertencia:</strong> Una vez confirmado, su voto es <strong>irreversible</strong> y su credencial quedará inutilizada permanentemente.
            </Alert>
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenConfirmModal(false)}>Cambiar Selección</Button>
            <Button
              variant="contained"
              color="primary"
              onClick={handleConfirmVote}
              sx={{ fontWeight: 700 }}
            >
              Sí, Confirmar y Emitir
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
};

export default PublicVote;
