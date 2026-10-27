import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Box,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Typography,
  Chip,
  Container,
  Divider,
} from '@mui/material';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import HowToVoteIcon from '@mui/icons-material/HowToVote';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import LogoutIcon from '@mui/icons-material/Logout';
import DashboardIcon from '@mui/icons-material/Dashboard';
import BallotIcon from '@mui/icons-material/Ballot';
import SchoolIcon from '@mui/icons-material/School';
import HistoryIcon from '@mui/icons-material/History';
import TheoGenLogo from './TheoGenLogo';
import { useAuth } from '../context/AuthContext';

const Navbar = () => {
  const { user, logout, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [anchorEl, setAnchorEl] = useState(null);

  const handleMenuOpen = (e) => setAnchorEl(e.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  const handleLogout = () => {
    handleMenuClose();
    logout();
    navigate('/login');
  };

  const navLinks = [
    { label: 'Dashboard', path: '/', icon: <DashboardIcon fontSize="small" /> },
    { label: 'Elecciones', path: '/elecciones', icon: <BallotIcon fontSize="small" /> },
    { label: 'Colegios', path: '/colegios', icon: <SchoolIcon fontSize="small" /> },
    { label: 'Auditoría', path: '/auditoria', icon: <HistoryIcon fontSize="small" /> },
  ];

  const isPublicVoting = location.pathname.startsWith('/votar');

  return (
    <AppBar position="sticky" sx={{ backgroundColor: '#0d233a', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
      <Container maxWidth="xl">
        <Toolbar disableGutters sx={{ minHeight: 70, display: 'flex', justifyContent: 'space-between' }}>
          {/* Logo */}
          <Link to="/" style={{ display: 'flex', alignItems: 'center' }}>
            <TheoGenLogo light />
          </Link>

          {/* Links Principales */}
          {!isPublicVoting && (
            <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1 }}>
              {navLinks.map((link) => {
                const isActive = location.pathname === link.path || (link.path !== '/' && location.pathname.startsWith(link.path));
                return (
                  <Button
                    key={link.path}
                    component={Link}
                    to={link.path}
                    startIcon={link.icon}
                    sx={{
                      color: isActive ? '#ffffff' : '#cbd5e1',
                      fontWeight: isActive ? 700 : 500,
                      backgroundColor: isActive ? 'rgba(255, 255, 255, 0.12)' : 'transparent',
                      borderRadius: '8px',
                      px: 1.8,
                      py: 0.9,
                      '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.18)',
                        color: '#ffffff',
                      },
                    }}
                  >
                    {link.label}
                  </Button>
                );
              })}
            </Box>
          )}

          {/* Acciones Derecha */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Botón de Acceso Rápido a Sala de Votación */}
            <Button
              component={Link}
              to="/votar"
              variant="contained"
              startIcon={<HowToVoteIcon />}
              sx={{
                background: 'linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)',
                color: '#ffffff',
                fontWeight: 700,
                borderRadius: '8px',
                px: 2.2,
                py: 0.9,
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.35)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%)',
                  boxShadow: '0 6px 18px rgba(37, 99, 235, 0.45)',
                },
              }}
            >
              Sala de Votación
            </Button>

            {/* Menú de Usuario o Iniciar Sesión */}
            {isAuthenticated ? (
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Button
                  onClick={handleMenuOpen}
                  sx={{
                    color: '#ffffff',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    textTransform: 'none',
                    p: 0.8,
                    borderRadius: '8px',
                    '&:hover': { backgroundColor: 'rgba(255, 255, 255, 0.1)' },
                  }}
                >
                  <AccountCircleIcon sx={{ fontSize: 26, color: '#93c5fd' }} />
                  <Box sx={{ textAlign: 'left', display: { xs: 'none', sm: 'block' } }}>
                    <Typography variant="body2" sx={{ fontWeight: 600, color: '#ffffff', lineHeight: 1.1 }}>
                      {user?.nombre || 'Usuario'}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#93c5fd', fontSize: '0.68rem' }}>
                      {user?.rol || 'Administrador'}
                    </Typography>
                  </Box>
                </Button>
                <Menu
                  anchorEl={anchorEl}
                  open={Boolean(anchorEl)}
                  onClose={handleMenuClose}
                  PaperProps={{
                    sx: {
                      mt: 1.5,
                      minWidth: 200,
                      borderRadius: 2,
                      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
                    },
                  }}
                >
                  <Box sx={{ px: 2, py: 1 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                      {user?.nombre}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {user?.email}
                    </Typography>
                    <Box sx={{ mt: 0.5 }}>
                      <Chip label={user?.rol} size="small" color="primary" sx={{ fontSize: '0.65rem', height: 20 }} />
                    </Box>
                  </Box>
                  <Divider />
                  <MenuItem onClick={handleLogout} sx={{ color: '#dc2626', gap: 1 }}>
                    <LogoutIcon fontSize="small" /> Cerrar Sesión
                  </MenuItem>
                </Menu>
              </Box>
            ) : (
              <Button
                component={Link}
                to="/login"
                variant="outlined"
                sx={{
                  color: '#ffffff',
                  borderColor: 'rgba(255, 255, 255, 0.3)',
                  '&:hover': { borderColor: '#ffffff', backgroundColor: 'rgba(255,255,255,0.08)' },
                }}
              >
                Ingresar
              </Button>
            )}
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navbar;
