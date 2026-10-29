import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Grid,
  TextField,
  MenuItem,
  Button,
  Alert,
  Divider,
  Paper,
  IconButton,
  RadioGroup,
  FormControlLabel,
  Radio,
  FormHelperText,
} from '@mui/material';
import { useNavigate, Link } from 'react-router-dom';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import { electionService, schoolService } from '../services/api';

const ELECTION_TYPES = [
  'Centro de Padres',
  'Centro de Alumnos',
  'Consejo Escolar',
  'Consulta Ciudadana',
  'Directiva Organización',
];

const ElectionCreate = () => {
  const navigate = useNavigate();
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Form State
  const [motor, setMotor] = useState('belenios');
  const [nombre, setNombre] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [schoolId, setSchoolId] = useState('');
  const [tipoVotacion, setTipoVotacion] = useState('Centro de Padres');
  const [reglaVotacion, setReglaVotacion] = useState('Un voto por persona');
  const [fechaInicio, setFechaInicio] = useState('');
  const [fechaFin, setFechaFin] = useState('');

  // Comisión Electoral Inicial
  const [committee, setCommittee] = useState([
    { nombre: '', rut: '', correo: '', cargo: 'Presidente(a) Comisión' },
    { nombre: '', rut: '', correo: '', cargo: 'Secretario(a) Comisión' },
    { nombre: '', rut: '', correo: '', cargo: 'Vocal de Control' },
  ]);

  useEffect(() => {
    const fetchSchools = async () => {
      try {
        const data = await schoolService.getAll();
        setSchools(data);
        if (data.length > 0) {
          setSchoolId(data[0].id);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchSchools();
  }, []);

  const handleCommitteeChange = (index, field, value) => {
    const updated = [...committee];
    updated[index][field] = value;
    setCommittee(updated);
  };

  const handleAddMember = () => {
    setCommittee([...committee, { nombre: '', rut: '', correo: '', cargo: 'Vocal de Mesa' }]);
  };

  const handleRemoveMember = (index) => {
    setCommittee(committee.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!nombre.trim() || !schoolId) {
      setError('Por favor complete el nombre de la elección y seleccione una institución.');
      return;
    }

    setLoading(true);
    try {
      // Filtrar miembros con al menos nombre y rut
      const validCommittee = committee.filter((m) => m.nombre.trim() && m.rut.trim());

      const payload = {
        nombre: nombre.trim(),
        descripcion: descripcion.trim() || null,
        school_id: Number(schoolId),
        tipo_votacion: tipoVotacion,
        motor,
        regla_votacion: reglaVotacion,
        fecha_inicio: fechaInicio ? new Date(fechaInicio).toISOString() : null,
        fecha_fin: fechaFin ? new Date(fechaFin).toISOString() : null,
        committee: validCommittee,
      };

      const created = await electionService.create(payload);
      navigate(`/elecciones/${created.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al crear la elección. Verifique los campos.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 3 }}>
        <Button component={Link} to="/elecciones" startIcon={<ArrowBackIcon />} sx={{ color: 'text.secondary', mb: 1 }}>
          Volver a Elecciones
        </Button>
        <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a' }}>
          Crear Nuevo Proceso Electoral
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Configure los parámetros fundamentales, tipo de proceso y reglas de emisión de sufragio
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
          {error}
        </Alert>
      )}

      <form onSubmit={handleSubmit}>
        <Grid container spacing={3}>
          {/* Módulo 1: Datos Generales */}
          <Grid item xs={12} md={7}>
            <Card sx={{ p: 1, borderRadius: 3, mb: 3 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a', mb: 2 }}>
                  1. Información Principal de la Elección
                </Typography>

                <TextField
                  fullWidth
                  label="Nombre de la Elección"
                  placeholder="ej: Elección Directiva Centro General de Padres 2026-2027"
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                  sx={{ mb: 2.5 }}
                />

                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Descripción y Propósito"
                  placeholder="Explique el objetivo y contexto de este proceso democrático..."
                  value={descripcion}
                  onChange={(e) => setDescripcion(e.target.value)}
                  sx={{ mb: 2.5 }}
                />

                <Grid container spacing={2} sx={{ mb: 2.5 }}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      select
                      fullWidth
                      label="Colegio u Organización"
                      value={schoolId}
                      onChange={(e) => setSchoolId(e.target.value)}
                      required
                    >
                      {schools.map((s) => (
                        <MenuItem key={s.id} value={s.id}>
                          {s.nombre} (RBD: {s.rbd || 'S/N'})
                        </MenuItem>
                      ))}
                    </TextField>
                  </Grid>

                  <Grid item xs={12}>
                    <TextField select fullWidth label="Motor electoral" value={motor} onChange={event => setMotor(event.target.value)}>
                      <MenuItem value="belenios">Belenios: padrón sin credenciales MVP; activación sujeta al entorno autorizado</MenuItem>
                      <MenuItem value="mvp">MVP: gestión y sufragio heredado con sus restricciones</MenuItem>
                    </TextField>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      select
                      fullWidth
                      label="Tipo de Votación"
                      value={tipoVotacion}
                      onChange={(e) => setTipoVotacion(e.target.value)}
                      required
                    >
                      {ELECTION_TYPES.map((t) => (
                        <MenuItem key={t} value={t}>
                          {t}
                        </MenuItem>
                      ))}
                    </TextField>
                  </Grid>
                </Grid>

                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="datetime-local"
                      label="Fecha y Hora de Inicio"
                      InputLabelProps={{ shrink: true }}
                      value={fechaInicio}
                      onChange={(e) => setFechaInicio(e.target.value)}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      type="datetime-local"
                      label="Fecha y Hora de Cierre Estimada"
                      InputLabelProps={{ shrink: true }}
                      value={fechaFin}
                      onChange={(e) => setFechaFin(e.target.value)}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Módulo 3: Regla Electoral */}
            <Card sx={{ p: 1, borderRadius: 3 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a', mb: 1 }}>
                  2. Configuración de Regla Electoral (Módulo 3)
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Establezca el criterio de emisión de voto según el estatuto institucional
                </Typography>

                <RadioGroup value={reglaVotacion} onChange={(e) => setReglaVotacion(e.target.value)}>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      mb: 2,
                      borderRadius: 2,
                      borderColor: reglaVotacion === 'Un voto por persona' ? '#1e40af' : '#e2e8f0',
                      backgroundColor: reglaVotacion === 'Un voto por persona' ? '#eff6ff' : '#ffffff',
                    }}
                  >
                    <FormControlLabel
                      value="Un voto por persona"
                      control={<Radio />}
                      label={
                        <Box>
                          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                            Un voto por persona
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Cada elector en el padrón dispone de su propio voto individual e intransferible. Ideal para Centros de Alumnos, Consejos Escolares y Consultas Ciudadanas.
                          </Typography>
                        </Box>
                      }
                    />
                  </Paper>

                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      borderRadius: 2,
                      borderColor: reglaVotacion === 'Un voto por familia' ? '#1e40af' : '#e2e8f0',
                      backgroundColor: reglaVotacion === 'Un voto por familia' ? '#eff6ff' : '#ffffff',
                    }}
                  >
                    <FormControlLabel
                      value="Un voto por familia"
                      control={<Radio />}
                      label={
                        <Box>
                          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                            Un voto por familia (Regla Centros de Padres)
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            El sistema asocia un <strong>familia_id</strong> a los apoderados. Una vez que un miembro sufraga, los demás quedan bloqueados automáticamente para evitar duplicidad.
                          </Typography>
                        </Box>
                      }
                    />
                  </Paper>
                </RadioGroup>
              </CardContent>
            </Card>
          </Grid>

          {/* Comisión Electoral Supervisora */}
          <Grid item xs={12} md={5}>
            <Card sx={{ p: 1, borderRadius: 3, mb: 3 }}>
              <CardContent sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                    3. Comisión Electoral
                  </Typography>
                  <Button size="small" startIcon={<PersonAddIcon />} onClick={handleAddMember}>
                    Añadir
                  </Button>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                  Supervisores acreditados para las Actas de Apertura y Cierre
                </Typography>

                {committee.map((member, idx) => (
                  <Paper
                    key={idx}
                    variant="outlined"
                    sx={{ p: 2, mb: 2, borderRadius: 2, backgroundColor: '#f8fafc' }}
                  >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                      <Typography variant="caption" sx={{ fontWeight: 700, color: '#1e40af' }}>
                        Miembro #{idx + 1}
                      </Typography>
                      {committee.length > 1 && (
                        <IconButton size="small" color="error" onClick={() => handleRemoveMember(idx)}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      )}
                    </Box>

                    <TextField
                      fullWidth
                      size="small"
                      label="Nombre Completo"
                      value={member.nombre}
                      onChange={(e) => handleCommitteeChange(idx, 'nombre', e.target.value)}
                      sx={{ mb: 1.5 }}
                      placeholder="ej: María Paz Edwards"
                    />

                    <Grid container spacing={1} sx={{ mb: 1.5 }}>
                      <Grid item xs={6}>
                        <TextField
                          fullWidth
                          size="small"
                          label="RUT"
                          value={member.rut}
                          onChange={(e) => handleCommitteeChange(idx, 'rut', e.target.value)}
                          placeholder="12.345.678-9"
                        />
                      </Grid>
                      <Grid item xs={6}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Cargo"
                          value={member.cargo}
                          onChange={(e) => handleCommitteeChange(idx, 'cargo', e.target.value)}
                        />
                      </Grid>
                    </Grid>

                    <TextField
                      fullWidth
                      size="small"
                      type="email"
                      label="Correo Electrónico"
                      value={member.correo}
                      onChange={(e) => handleCommitteeChange(idx, 'correo', e.target.value)}
                      placeholder="mpaz@ejemplo.cl"
                    />
                  </Paper>
                ))}
              </CardContent>
            </Card>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading}
              startIcon={<CheckCircleIcon />}
              sx={{
                py: 1.6,
                fontWeight: 700,
                fontSize: '1.05rem',
                backgroundColor: '#0d233a',
                boxShadow: '0 4px 15px rgba(13, 35, 58, 0.25)',
                '&:hover': { backgroundColor: '#1e40af' },
              }}
            >
              {loading ? 'Creando Elección...' : 'Crear y Continuar al Hub'}
            </Button>
          </Grid>
        </Grid>
      </form>
    </Container>
  );
};

export default ElectionCreate;
