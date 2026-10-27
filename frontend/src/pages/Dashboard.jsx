import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  LinearProgress,
} from '@mui/material';
import { Link, useNavigate } from 'react-router-dom';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import PeopleAltOutlinedIcon from '@mui/icons-material/PeopleAltOutlined';
import CheckCircleOutlinedIcon from '@mui/icons-material/CheckCircleOutlined';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import HourglassTopIcon from '@mui/icons-material/HourglassTop';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import AssessmentOutlinedIcon from '@mui/icons-material/AssessmentOutlined';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  PieChart,
  Pie,
} from 'recharts';

import { reportService, electionService } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [elections, setElections] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, electionsData] = await Promise.all([
          reportService.getDashboardStats(),
          electionService.getAll(),
        ]);
        setStats(statsData);
        setElections(electionsData);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress sx={{ color: '#0d233a' }} />
      </Box>
    );
  }

  // Preparar datos para gráficos
  const chartData = elections.map((el) => ({
    name: el.nombre.length > 25 ? el.nombre.substring(0, 22) + '...' : el.nombre,
    estado: el.estado,
    tipo: el.tipo_votacion,
  }));

  const pieData = [
    { name: 'Votos Emitidos', value: stats?.total_votos_emitidos || 0, color: '#059669' },
    {
      name: 'Votos Pendientes',
      value: Math.max(0, (stats?.total_padron || 0) - (stats?.total_votos_emitidos || 0)),
      color: '#3b82f6',
    },
  ];

  const statCards = [
    {
      title: 'Total Padrón Habilitado',
      value: stats?.total_padron || 0,
      subtitle: 'Electores registrados en el sistema',
      icon: <PeopleAltOutlinedIcon sx={{ fontSize: 28, color: '#1e40af' }} />,
      bgColor: '#eff6ff',
      borderColor: '#bfdbfe',
    },
    {
      title: 'Total Votos Emitidos',
      value: stats?.total_votos_emitidos || 0,
      subtitle: 'Sufragios verificados con integridad',
      icon: <CheckCircleOutlinedIcon sx={{ fontSize: 28, color: '#059669' }} />,
      bgColor: '#ecfdf5',
      borderColor: '#a7f3d0',
    },
    {
      title: 'Participación Global',
      value: `${stats?.participacion_global || 0}%`,
      subtitle: 'Tasa de sufragio promedio',
      icon: <TrendingUpIcon sx={{ fontSize: 28, color: '#d97706' }} />,
      bgColor: '#fffbeb',
      borderColor: '#fde68a',
    },
    {
      title: 'Votos Pendientes',
      value: Math.max(0, (stats?.total_padron || 0) - (stats?.total_votos_emitidos || 0)),
      subtitle: 'Electores por sufragar',
      icon: <HourglassTopIcon sx={{ fontSize: 28, color: '#7c3aed' }} />,
      bgColor: '#f5f3ff',
      borderColor: '#ddd6fe',
    },
  ];

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Banner de Bienvenida y Acceso Directo al Demo */}
      <Card
        sx={{
          mb: 4,
          background: 'linear-gradient(135deg, #0d233a 0%, #1e40af 100%)',
          color: '#ffffff',
          borderRadius: 3,
          p: 1,
          boxShadow: '0 10px 25px -5px rgba(13, 35, 58, 0.25)',
        }}
      >
        <CardContent sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', md: 'row' }, alignItems: { md: 'center' }, justifyContent: 'space-between', gap: 2 }}>
          <Box>
            <Chip
              label="DEMO OPERACIONAL THEOGEN ELECTORAL"
              size="small"
              sx={{
                backgroundColor: 'rgba(255, 255, 255, 0.15)',
                color: '#93c5fd',
                fontWeight: 700,
                letterSpacing: '0.05em',
                mb: 1.5,
              }}
            />
            <Typography variant="h4" sx={{ fontWeight: 800, mb: 1, letterSpacing: '-0.02em' }}>
              Gestión Electoral Transparente y Verificable
            </Typography>
            <Typography variant="body1" sx={{ color: 'rgba(255, 255, 255, 0.85)', maxWidth: 700 }}>
              Diseñada para colegios, centros de padres y organizaciones sociales. Gestione padrones, configure reglas familiares, genere credenciales únicas y emita votos con hash de integridad.
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              component={Link}
              to="/votar"
              variant="contained"
              size="large"
              startIcon={<HowToVoteIcon />}
              sx={{
                backgroundColor: '#ffffff',
                color: '#0d233a',
                fontWeight: 700,
                px: 3,
                py: 1.3,
                boxShadow: '0 4px 14px rgba(0,0,0,0.2)',
                '&:hover': { backgroundColor: '#f1f5f9' },
              }}
            >
              Probar Sala de Votación
            </Button>
            <Button
              component={Link}
              to="/elecciones/nueva"
              variant="outlined"
              size="large"
              startIcon={<AddCircleIcon />}
              sx={{
                borderColor: 'rgba(255, 255, 255, 0.4)',
                color: '#ffffff',
                fontWeight: 600,
                px: 2.5,
                '&:hover': { borderColor: '#ffffff', backgroundColor: 'rgba(255,255,255,0.1)' },
              }}
            >
              Crear Elección
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Tarjetas de Métricas Estadísticas (Módulo 6) */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        {statCards.map((card, idx) => (
          <Grid item xs={12} sm={6} md={3} key={idx}>
            <Card
              sx={{
                height: '100%',
                p: 1,
                border: `1px solid ${card.borderColor}`,
                borderRadius: 3,
                backgroundColor: '#ffffff',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                '&:hover': {
                  transform: 'translateY(-3px)',
                  boxShadow: '0 10px 20px -3px rgba(15, 23, 42, 0.08)',
                },
              }}
            >
              <CardContent sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.secondary' }}>
                    {card.title}
                  </Typography>
                  <Box
                    sx={{
                      width: 44,
                      height: 44,
                      borderRadius: '10px',
                      backgroundColor: card.bgColor,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {card.icon}
                  </Box>
                </Box>
                <Typography variant="h3" sx={{ fontWeight: 800, color: '#0d233a', mb: 0.5 }}>
                  {card.value}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {card.subtitle}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Gráficos Visuales y Participación */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={7}>
          <Card sx={{ p: 2, height: '100%', borderRadius: 3 }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                    Avance de Participación Electoral
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Porcentaje de sufragios recibidos respecto al padrón habilitado
                  </Typography>
                </Box>
                <Chip label={`${stats?.participacion_global || 0}% Participación`} color="success" size="small" />
              </Box>

              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    Progreso General de Sufragios
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700, color: '#059669' }}>
                    {stats?.total_votos_emitidos || 0} de {stats?.total_padron || 0} electores
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={Number(stats?.participacion_global) || 0}
                  sx={{
                    height: 12,
                    borderRadius: 6,
                    backgroundColor: '#e2e8f0',
                    '& .MuiLinearProgress-bar': {
                      borderRadius: 6,
                      background: 'linear-gradient(90deg, #1e40af 0%, #059669 100%)',
                    },
                  }}
                />
              </Box>

              <Box sx={{ height: 200, width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={pieData} layout="vertical" margin={{ top: 10, right: 30, left: 40, bottom: 0 }}>
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={120} />
                    <Tooltip />
                    <Bar dataKey="value" radius={[0, 8, 8, 0]}>
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={5}>
          <Card sx={{ p: 2, height: '100%', borderRadius: 3 }}>
            <CardContent>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a', mb: 1 }}>
                Distribución de Votos
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
                Relación entre electores participantes y abstención temporal
              </Typography>

              <Box sx={{ height: 230, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={4}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-pie-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#059669' }} />
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    Emitidos ({stats?.total_votos_emitidos || 0})
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#3b82f6' }} />
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    Pendientes ({Math.max(0, (stats?.total_padron || 0) - (stats?.total_votos_emitidos || 0))})
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabla de Elecciones Recientes */}
      <Card sx={{ borderRadius: 3 }}>
        <CardContent sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a' }}>
                Procesos Electorales Activos
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Elecciones configuradas en la plataforma
              </Typography>
            </Box>
            <Button
              component={Link}
              to="/elecciones"
              endIcon={<ArrowForwardIcon />}
              sx={{ fontWeight: 600 }}
            >
              Ver Todas las Elecciones
            </Button>
          </Box>

          <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 2 }}>
            <Table>
              <TableHead sx={{ backgroundColor: '#f8fafc' }}>
                <TableRow>
                  <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Nombre de la Elección</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Colegio / Institución</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Tipo Votación</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Regla Electoral</TableCell>
                  <TableCell sx={{ fontWeight: 700, color: '#475569' }}>Estado</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: '#475569' }}>Acciones</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {elections.map((election) => (
                  <TableRow key={election.id} hover>
                    <TableCell>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#0d233a' }}>
                        {election.nombre}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        ID: #{election.id}
                      </Typography>
                    </TableCell>
                    <TableCell>{election.school?.nombre || 'Colegio San Gabriel'}</TableCell>
                    <TableCell>
                      <Chip label={election.tipo_votacion} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={election.regla_votacion}
                        size="small"
                        sx={{
                          backgroundColor: election.regla_votacion.includes('familia') ? '#fdf4ff' : '#eff6ff',
                          color: election.regla_votacion.includes('familia') ? '#86198f' : '#1e40af',
                          fontWeight: 600,
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={election.estado} />
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        variant="outlined"
                        component={Link}
                        to={`/elecciones/${election.id}`}
                        sx={{ mr: 1, fontWeight: 600 }}
                      >
                        Gestionar
                      </Button>
                      <Button
                        size="small"
                        variant="contained"
                        color="primary"
                        component={Link}
                        to={`/elecciones/${election.id}#escrutinio`}
                        startIcon={<AssessmentOutlinedIcon />}
                        sx={{ fontWeight: 600 }}
                      >
                        Resultados
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Dashboard;
