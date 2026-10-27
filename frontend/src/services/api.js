import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

// Interceptor para inyectar token JWT automáticamente
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('theogen_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Interceptor para manejo de errores de autenticación
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Si el token expira o es inválido en rutas protegidas
      if (!window.location.pathname.startsWith('/votar') && window.location.pathname !== '/login') {
        localStorage.removeItem('theogen_token');
        localStorage.removeItem('theogen_user');
      }
    }
    return Promise.reject(error);
  }
);

export const authService = {
  login: async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    return res.data;
  },
  getMe: async () => {
    const res = await api.get('/auth/me');
    return res.data;
  },
};

export const schoolService = {
  getAll: async () => {
    const res = await api.get('/schools');
    return res.data;
  },
  create: async (schoolData) => {
    const res = await api.post('/schools', schoolData);
    return res.data;
  },
  getById: async (id) => {
    const res = await api.get(`/schools/${id}`);
    return res.data;
  },
};

export const electionService = {
  getAll: async () => {
    const res = await api.get('/elections');
    return res.data;
  },
  getById: async (id) => {
    const res = await api.get(`/elections/${id}`);
    return res.data;
  },
  create: async (data) => {
    const res = await api.post('/elections', data);
    return res.data;
  },
  update: async (id, data) => {
    const res = await api.put(`/elections/${id}`, data);
    return res.data;
  },
  open: async (id) => {
    const res = await api.post(`/elections/${id}/abrir`);
    return res.data;
  },
  close: async (id) => {
    const res = await api.post(`/elections/${id}/cerrar`);
    return res.data;
  },
  addCommitteeMember: async (electionId, memberData) => {
    const res = await api.post(`/elections/${electionId}/comite`, memberData);
    return res.data;
  },
};

export const voterService = {
  getByElection: async (electionId, params = {}) => {
    const res = await api.get(`/elections/${electionId}/voters`, { params });
    return res.data;
  },
  create: async (electionId, voterData) => {
    const res = await api.post(`/elections/${electionId}/voters`, voterData);
    return res.data;
  },
  uploadExcel: async (electionId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await api.post(`/elections/${electionId}/voters/upload-excel`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  generateTokens: async (electionId) => {
    const res = await api.post(`/elections/${electionId}/voters/generate-tokens`);
    return res.data;
  },
  getEmailSimulation: async (electionId) => {
    const res = await api.get(`/elections/${electionId}/voters/simulate-email-dispatch`);
    return res.data;
  },
  getTemplateDownloadUrl: (electionId) => `/api/elections/${electionId}/voters/template`,
};

export const candidateService = {
  getByElection: async (electionId) => {
    const res = await api.get(`/elections/${electionId}/candidates`);
    return res.data;
  },
  create: async (electionId, data) => {
    const res = await api.post(`/elections/${electionId}/candidates`, data);
    return res.data;
  },
  delete: async (electionId, candidateId) => {
    const res = await api.delete(`/elections/${electionId}/candidates/${candidateId}`);
    return res.data;
  },
};

export const votingService = {
  validateToken: async (token) => {
    const res = await api.post(`/voting/validate-token?token=${encodeURIComponent(token)}`);
    return res.data;
  },
  submitVote: async (token, candidateId) => {
    const res = await api.post('/voting/submit', { token, candidate_id: candidateId });
    return res.data;
  },
};

export const reportService = {
  getScrutiny: async (electionId) => {
    const res = await api.get(`/reports/election/${electionId}/scrutiny`);
    return res.data;
  },
  getDashboardStats: async () => {
    const res = await api.get('/reports/dashboard-stats');
    return res.data;
  },
  getActaAperturaPdfUrl: (electionId) => {
    const token = localStorage.getItem('theogen_token');
    return `/api/reports/election/${electionId}/acta-apertura/pdf${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getActaCierrePdfUrl: (electionId) => {
    const token = localStorage.getItem('theogen_token');
    return `/api/reports/election/${electionId}/acta-cierre/pdf${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
};

export const auditService = {
  getLogs: async (params = {}) => {
    const res = await api.get('/audit/logs', { params });
    return res.data;
  },
};

export default api;
