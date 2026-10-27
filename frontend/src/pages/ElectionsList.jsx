import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Card,
  CardContent,
  Grid,
  TextField,
  InputAdornment,
  MenuItem,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import { Link } from 'react-router-dom';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import SearchIcon from '@mui/icons-material/Search';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import SchoolIcon from '@mui/icons-material/School';
import AssessmentIcon from '@mui/icons-material/Assessment';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import { electionService } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const ElectionsList = () => {
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('TODOS');

  useEffect(() => {
    loadElections();
  }, []);

  const loadElections = async () => {
    try {
      const data = await electionService.getAll();
      setElections(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredElections = elections.filter((el) => {
    const matchesSearch =
      el.nombre.toLowerCase().includes(search.toLowerCase()) ||
      el.tipo_votacion.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'TODOS' || el.estado === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a', mb: 0.5 }}>
            Procesos Electorales
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Administración de votaciones, padrones, comisiones y actas oficiales
          </Typography>
        </Box>
        <Button
          component={Link}
          to="/elecciones/nueva"
          variant="contained"
          size="large"
          startIcon={<AddCircleIcon />}
          sx={{
            backgroundColor: '#0d233a',
            fontWeight: 700,
            px: 3,
            '&:hover': { backgroundColor: '#163a63' },
          }}
        >
          Crear Elección
        </Button>
      </Box>

      {/* Filtros y Búsqueda */}
      <Card sx={{ mb: 4, borderRadius: 2 }}>
        <CardContent sx={{ p: 2 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={7}>
              <TextField
                fullWidth
                size="small"
                placeholder="Buscar por nombre de elección o tipo..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon color="action" />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={5}>
              <TextField
                select
                fullWidth
                size="small"
                label="Filtrar por Estado"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <MenuItem value="TODOS">Todos los Estados</MenuItem>
                <MenuItem value="Abierta">Abierta</MenuItem>
                <MenuItem value="Borrador">Borrador</MenuItem>
                <MenuItem value="Cerrada">Cerrada</MenuItem>
                <MenuItem value="Finalizada">Finalizada</MenuItem>
              </TextField>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {loading ? (
        <LinearProgress sx={{ my: 4 }} />
      ) : filteredElections.length === 0 ? (
        <Card sx={{ p: 6, textAlign: 'center', borderRadius: 3, backgroundColor: '#f8fafc' }}>
          <Typography variant="h6" color="text.secondary" sx={{ mb: 2 }}>
            No se encontraron procesos electorales
          </Typography>
          <Button component={Link} to="/elecciones/nueva" variant="contained">
            Crear la Primera Elección
          </Button>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {filteredElections.map((election) => (
            <Grid item xs={12} md={6} lg={4} key={election.id}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  borderRadius: 3,
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: '0 12px 24px -4px rgba(13, 35, 58, 0.1)',
                  },
                }}
              >
                <CardContent sx={{ p: 3, flexGrow: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <StatusBadge status={election.estado} />
                    <Chip
                      label={election.tipo_votacion}
                      size="small"
                      variant="outlined"
                      sx={{ fontWeight: 600, fontSize: '0.7rem' }}
                    />
                  </Box>

                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 700,
                      color: '#0d233a',
                      lineHeight: 1.3,
                      mb: 1.5,
                      minHeight: 52,
                    }}
                  >
                    {election.nombre}
                  </Typography>

                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      mb: 2.5,
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      minHeight: 40,
                    }}
                  >
                    {election.descripcion || 'Sin descripción detallada del proceso eleccionario.'}
                  </Typography>

                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <SchoolIcon sx={{ fontSize: 18, color: '#64748b' }} />
                      <Typography variant="caption" sx={{ color: '#475569', fontWeight: 600 }}>
                        {election.school?.nombre || 'Colegio Registrado'}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CalendarMonthIcon sx={{ fontSize: 18, color: '#64748b' }} />
                      <Typography variant="caption" sx={{ color: '#475569' }}>
                        Regla: <strong>{election.regla_votacion}</strong>
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>

                <Box
                  sx={{
                    p: 2,
                    pt: 0,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderTop: '1px solid #f1f5f9',
                    backgroundColor: '#fafbfc',
                  }}
                >
                  <Button
                    component={Link}
                    to={`/elecciones/${election.id}#escrutinio`}
                    size="small"
                    startIcon={<AssessmentIcon />}
                    sx={{ color: '#059669', fontWeight: 600 }}
                  >
                    Escrutinio
                  </Button>
                  <Button
                    component={Link}
                    to={`/elecciones/${election.id}`}
                    size="small"
                    variant="contained"
                    endIcon={<ArrowForwardIcon />}
                    sx={{
                      backgroundColor: '#0d233a',
                      fontWeight: 600,
                      '&:hover': { backgroundColor: '#1e40af' },
                    }}
                  >
                    Administrar
                  </Button>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
};

export default ElectionsList;
