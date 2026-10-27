import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  InputAdornment,
  MenuItem,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import HistoryIcon from '@mui/icons-material/History';
import SecurityIcon from '@mui/icons-material/Security';
import { auditService } from '../services/api';

const ACTION_COLORS = {
  'Creó elección': 'primary',
  'Subió padrón': 'secondary',
  'Abrió votación': 'success',
  'Emitió voto': 'info',
  'Cerró votación': 'warning',
  'Descargó acta': 'default',
};

const AuditLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('TODAS');

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    try {
      setLoading(true);
      const data = await auditService.getLogs({ limit: 100 });
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.accion.toLowerCase().includes(search.toLowerCase()) ||
      log.usuario.toLowerCase().includes(search.toLowerCase()) ||
      (log.detalle && log.detalle.toLowerCase().includes(search.toLowerCase()));
    const matchesAction = actionFilter === 'TODAS' || log.accion.toLowerCase() === actionFilter.toLowerCase();
    return matchesSearch && matchesAction;
  });

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Encabezado */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
            <SecurityIcon sx={{ color: '#0d233a', fontSize: 30 }} />
            <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a' }}>
              Trazabilidad y Auditoría (Módulo 9)
            </Typography>
          </Box>
          <Typography variant="body1" color="text.secondary">
            Registro inmutable de todas las operaciones realizadas en la plataforma electoral
          </Typography>
        </Box>
        <Tooltip title="Actualizar Bitácora">
          <IconButton onClick={loadLogs} sx={{ backgroundColor: '#ffffff', border: '1px solid #cbd5e1' }}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Filtros */}
      <Card sx={{ mb: 3, borderRadius: 2 }}>
        <CardContent sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              sx={{ flexGrow: 1 }}
              size="small"
              placeholder="Buscar por usuario, acción o detalle..."
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
            <TextField
              select
              size="small"
              sx={{ minWidth: 220 }}
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            >
              <MenuItem value="TODAS">Todas las Acciones</MenuItem>
              <MenuItem value="Creó elección">Creó elección</MenuItem>
              <MenuItem value="Subió padrón">Subió padrón</MenuItem>
              <MenuItem value="Abrió votación">Abrió votación</MenuItem>
              <MenuItem value="Emitió voto">Emitió voto</MenuItem>
              <MenuItem value="Cerró votación">Cerró votación</MenuItem>
              <MenuItem value="Descargó acta">Descargó acta</MenuItem>
            </TextField>
          </Box>
        </CardContent>
      </Card>

      {loading ? (
        <LinearProgress sx={{ my: 4 }} />
      ) : (
        <TableContainer component={Paper} sx={{ borderRadius: 2, border: '1px solid #e2e8f0' }}>
          <Table>
            <TableHead sx={{ backgroundColor: '#f8fafc' }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700, width: 80 }}>ID</TableCell>
                <TableCell sx={{ fontWeight: 700, width: 180 }}>Fecha y Hora</TableCell>
                <TableCell sx={{ fontWeight: 700, width: 220 }}>Usuario / Origen</TableCell>
                <TableCell sx={{ fontWeight: 700, width: 170 }}>Acción Registrada</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Detalle de la Operación</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredLogs.map((log) => {
                const dateObj = new Date(log.fecha);
                const formattedDate = dateObj.toLocaleString('es-CL', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                });

                return (
                  <TableRow key={log.id} hover>
                    <TableCell sx={{ fontWeight: 600, color: 'text.secondary' }}>#{log.id}</TableCell>
                    <TableCell sx={{ fontSize: '0.85rem' }}>{formattedDate}</TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600, color: '#0d233a' }}>
                        {log.usuario}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={log.accion}
                        size="small"
                        color={ACTION_COLORS[log.accion] || 'default'}
                        sx={{ fontWeight: 700 }}
                      />
                    </TableCell>
                    <TableCell sx={{ fontSize: '0.9rem', color: '#334155' }}>
                      {log.detalle}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  );
};

export default AuditLogs;
