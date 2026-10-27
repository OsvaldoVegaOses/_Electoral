import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  Divider,
  Container,
  Paper,
} from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import LockOpenIcon from '@mui/icons-material/LockOpen';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
import HowToRegIcon from '@mui/icons-material/HowToReg';
import TheoGenLogo from '../components/TheoGenLogo';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al iniciar sesión. Verifique sus credenciales.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = (demoEmail, demoPass) => {
    setEmail(demoEmail);
    setPassword(demoPass);
  };

  return (
    <Box
      sx={{
        minHeight: 'calc(100vh - 70px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        py: 6,
        background: 'radial-gradient(circle at 50% 20%, #eff6ff 0%, #f8fafc 100%)',
      }}
    >
      <Container maxWidth="sm">
        <Box sx={{ textAlign: 'center', mb: 3 }}>
          <Box sx={{ display: 'inline-flex', mb: 1 }}>
            <TheoGenLogo />
          </Box>
          <Typography variant="body2" color="text.secondary">
            Acceso administrativo y supervisión de procesos electorales
          </Typography>
        </Box>

        <Card sx={{ p: 2, boxShadow: '0 10px 30px rgba(13, 35, 58, 0.08)', borderRadius: 3 }}>
          <CardContent sx={{ p: 3 }}>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1, color: '#0d233a' }}>
              Iniciar Sesión
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Ingrese sus credenciales de Administrador o Comisión Electoral
            </Typography>

            {error && (
              <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <TextField
                fullWidth
                label="Correo Electrónico"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                sx={{ mb: 2 }}
                placeholder="ej: admin@theogen.cl"
              />

              <TextField
                fullWidth
                label="Contraseña"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                sx={{ mb: 3 }}
                placeholder="••••••••"
              />

              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading}
                startIcon={<LockOpenIcon />}
                sx={{
                  py: 1.3,
                  fontWeight: 700,
                  fontSize: '1rem',
                  backgroundColor: '#0d233a',
                  '&:hover': { backgroundColor: '#163a63' },
                }}
              >
                {loading ? 'Accediendo...' : 'Entrar a la Plataforma'}
              </Button>
            </form>

            <Divider sx={{ my: 3 }}>
              <Typography variant="caption" sx={{ color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Credenciales Demo Rápidas
              </Typography>
            </Divider>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  backgroundColor: '#f8fafc',
                  cursor: 'pointer',
                  '&:hover': { borderColor: '#1e40af', backgroundColor: '#eff6ff' },
                }}
                onClick={() => handleQuickLogin('admin@theogen.cl', 'admin123')}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <AdminPanelSettingsIcon sx={{ color: '#1e40af' }} />
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Administrador General
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      admin@theogen.cl / admin123
                    </Typography>
                  </Box>
                </Box>
                <Button size="small" variant="text" sx={{ fontWeight: 700 }}>
                  Autocompletar
                </Button>
              </Paper>

              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  backgroundColor: '#f8fafc',
                  cursor: 'pointer',
                  '&:hover': { borderColor: '#059669', backgroundColor: '#ecfdf5' },
                }}
                onClick={() => handleQuickLogin('comision@theogen.cl', 'comision123')}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <HowToRegIcon sx={{ color: '#059669' }} />
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      Comisión Electoral
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      comision@theogen.cl / comision123
                    </Typography>
                  </Box>
                </Box>
                <Button size="small" variant="text" color="success" sx={{ fontWeight: 700 }}>
                  Autocompletar
                </Button>
              </Paper>
            </Box>
          </CardContent>
        </Card>
      </Container>
    </Box>
  );
};

export default Login;
