import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  Paper,
  Divider,
} from '@mui/material';
import SchoolIcon from '@mui/icons-material/School';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import EmailIcon from '@mui/icons-material/Email';
import PhoneIcon from '@mui/icons-material/Phone';
import NumbersIcon from '@mui/icons-material/Numbers';
import { schoolService } from '../services/api';

const SchoolsManagement = () => {
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openModal, setOpenModal] = useState(false);
  const [error, setError] = useState('');
  const [newSchool, setNewSchool] = useState({
    nombre: '',
    rbd: '',
    comuna: '',
    correo_contacto: '',
    telefono: '',
    logo: '',
  });

  useEffect(() => {
    loadSchools();
  }, []);

  const loadSchools = async () => {
    try {
      setLoading(true);
      const data = await schoolService.getAll();
      setSchools(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSchool = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await schoolService.create(newSchool);
      setOpenModal(false);
      setNewSchool({ nombre: '', rbd: '', comuna: '', correo_contacto: '', telefono: '', logo: '' });
      loadSchools();
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar la institución.');
    }
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4, flexWrap: 'wrap', gap: 2 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 800, color: '#0d233a', mb: 0.5 }}>
            Colegios e Instituciones Registradas
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Entidades educativas, juntas de vecinos y organizaciones sociales organizadoras
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddCircleIcon />}
          onClick={() => setOpenModal(true)}
          sx={{ backgroundColor: '#0d233a', fontWeight: 700 }}
        >
          Registrar Colegio
        </Button>
      </Box>

      <Grid container spacing={3}>
        {schools.map((school) => (
          <Grid item xs={12} sm={6} md={4} key={school.id}>
            <Card sx={{ height: '100%', borderRadius: 3, border: '1px solid #e2e8f0' }}>
              <CardContent sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                  <Box
                    sx={{
                      width: 50,
                      height: 50,
                      borderRadius: '12px',
                      backgroundColor: '#eff6ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#1e40af',
                    }}
                  >
                    <SchoolIcon sx={{ fontSize: 28 }} />
                  </Box>
                  <Box>
                    <Typography variant="h6" sx={{ fontWeight: 700, color: '#0d233a', lineHeight: 1.2 }}>
                      {school.nombre}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      RBD: {school.rbd || 'Sin RBD'}
                    </Typography>
                  </Box>
                </Box>

                <Divider sx={{ my: 1.5 }} />

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <LocationOnIcon sx={{ fontSize: 18, color: '#64748b' }} />
                    <Typography variant="body2" color="text.secondary">
                      {school.comuna || 'No especificada'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <EmailIcon sx={{ fontSize: 18, color: '#64748b' }} />
                    <Typography variant="body2" color="text.secondary">
                      {school.correo_contacto || 'contacto@institucion.cl'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <PhoneIcon sx={{ fontSize: 18, color: '#64748b' }} />
                    <Typography variant="body2" color="text.secondary">
                      {school.telefono || '+56 2 2000 0000'}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      {/* Modal Crear Colegio */}
      <Dialog open={openModal} onClose={() => setOpenModal(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleCreateSchool}>
          <DialogTitle sx={{ fontWeight: 700, color: '#0d233a' }}>Registrar Nueva Institución / Colegio</DialogTitle>
          <DialogContent dividers>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <TextField
              fullWidth
              label="Nombre de la Institución"
              placeholder="ej: Colegio San Gabriel de Las Condes"
              value={newSchool.nombre}
              onChange={(e) => setNewSchool({ ...newSchool, nombre: e.target.value })}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="RBD o Identificador Oficial"
              placeholder="ej: 10245-8"
              value={newSchool.rbd}
              onChange={(e) => setNewSchool({ ...newSchool, rbd: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Comuna y Región"
              placeholder="ej: Las Condes, Santiago"
              value={newSchool.comuna}
              onChange={(e) => setNewSchool({ ...newSchool, comuna: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              type="email"
              label="Correo de Contacto"
              placeholder="contacto@colegio.cl"
              value={newSchool.correo_contacto}
              onChange={(e) => setNewSchool({ ...newSchool, correo_contacto: e.target.value })}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Teléfono"
              placeholder="+56 9 1234 5678"
              value={newSchool.telefono}
              onChange={(e) => setNewSchool({ ...newSchool, telefono: e.target.value })}
            />
          </DialogContent>
          <DialogActions sx={{ p: 2 }}>
            <Button onClick={() => setOpenModal(false)}>Cancelar</Button>
            <Button type="submit" variant="contained">Guardar Institución</Button>
          </DialogActions>
        </form>
      </Dialog>
    </Container>
  );
};

export default SchoolsManagement;
