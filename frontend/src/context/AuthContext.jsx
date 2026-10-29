import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('theogen_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        // P2: Verificar sesión activa contra el servidor usando la cookie HttpOnly
        const userData = await authService.getMe();
        setUser(userData);
        localStorage.setItem('theogen_user', JSON.stringify(userData));
      } catch {
        setUser(null);
        localStorage.removeItem('theogen_user');
        localStorage.removeItem('theogen_token');
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, []);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    // P2: El JWT ya NO se guarda en localStorage; viaja protegido en cookie HttpOnly
    localStorage.removeItem('theogen_token');
    localStorage.setItem('theogen_user', JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await authService.logout();
    } finally {
      localStorage.removeItem('theogen_token');
      localStorage.removeItem('theogen_user');
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
