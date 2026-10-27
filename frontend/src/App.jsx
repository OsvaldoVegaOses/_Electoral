import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box } from '@mui/material';
import theme from './theme';
import { AuthProvider, useAuth } from './context/AuthContext';

// Components
import Navbar from './components/Navbar';

// Pages
import Dashboard from './pages/Dashboard';
import ElectionsList from './pages/ElectionsList';
import ElectionCreate from './pages/ElectionCreate';
import ElectionDetail from './pages/ElectionDetail';
import SchoolsManagement from './pages/SchoolsManagement';
import AuditLogs from './pages/AuditLogs';
import PublicVote from './pages/PublicVote';
import Login from './pages/Login';

// Ruta protegida para usuarios autenticados si se requiere en el futuro
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <Router>
          <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#f8fafc' }}>
            <Navbar />
            <Box component="main" sx={{ flexGrow: 1 }}>
              <Routes>
                {/* Rutas Principales de TheoGen Electoral */}
                <Route path="/" element={<Dashboard />} />
                <Route path="/elecciones" element={<ElectionsList />} />
                <Route path="/elecciones/nueva" element={<ElectionCreate />} />
                <Route path="/elecciones/:id" element={<ElectionDetail />} />
                <Route path="/colegios" element={<SchoolsManagement />} />
                <Route path="/auditoria" element={<AuditLogs />} />
                
                {/* Sala de Votación Pública (Abierta sin autenticación administrativa) */}
                <Route path="/votar" element={<PublicVote />} />
                
                {/* Login Administrativo */}
                <Route path="/login" element={<Login />} />

                {/* Redirección por defecto */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Box>
          </Box>
        </Router>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
