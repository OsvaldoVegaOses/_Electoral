import axios from 'axios';

function getCookie(name) {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'));
  return match ? decodeURIComponent(match[3]) : null;
}

const api = axios.create({
  baseURL: '/api',
  withCredentials: true, // P2: Habilitar envío automático de cookies HttpOnly y CSRF
});

// Interceptor para inyectar token CSRF y credenciales de autenticación
api.interceptors.request.use((config) => {
  // P2: Adjuntar token CSRF desde cookie en cabecera X-CSRF-Token para mutaciones
  const csrfToken = getCookie('csrf_token');
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }

  // Fallback retrocompatible para Authorization si existiera token en almacenamiento
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
      // Si la sesión expira o es inválida en rutas protegidas
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
  logout: async () => {
    try {
      const res = await api.post('/auth/logout');
      return res.data;
    } catch {
      // Proceder localmente si la red falla
      return null;
    }
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

export const beleniosService = {
  status: async id => (await api.get(`/elections/${id}/belenios`)).data,
  prepare: async (id, body) => (await api.post(`/elections/${id}/belenios/prepare`, body)).data,
  transition: async (id, action) => (await api.post(`/elections/${id}/belenios/transition`, { action, request_id: crypto.randomUUID() })).data,
  verify: async (id, body) => (await api.post(`/elections/${id}/belenios/verify`, body)).data,
  units: async id => (await api.get(`/elections/${id}/belenios/units`)).data,
  record: async id => (await api.get(`/elections/${id}/belenios/record`)).data,
  reconcile: async (id, body) => (await api.post(`/elections/${id}/belenios/reconcile`, body)).data,
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

export const credentialDeliveryService = {
  list: async (election, voter) => (await api.get(`/elections/${election}/voters/${voter}/deliveries`)).data,
  issue: async (election, voter, operation) => (await api.post(`/elections/${election}/voters/${voter}/deliveries`, { operation_id: operation })).data,
  reconcile: async (election, voter, operation) => (await api.post(`/elections/${election}/voters/${voter}/deliveries/${operation}/reconcile`)).data,
};

export async function downloadBeleniosRecord(election) {
  const response = await api.get(`/elections/${election}/belenios/record/pdf`, { responseType: 'blob' });
  const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
  const link = document.createElement('a'); link.href = url; link.download = `Expediente_Belenios_${election}.pdf`;
  link.click(); URL.revokeObjectURL(url);
}

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
    const res = await api.post('/voting/validate-token', { token });
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
  downloadActaAperturaPdf: async (electionId, fileName) => {
    const res = await api.get(`/reports/election/${electionId}/acta-apertura/pdf`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName || `Acta_Apertura_Eleccion_${electionId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  downloadActaCierrePdf: async (electionId, fileName) => {
    const res = await api.get(`/reports/election/${electionId}/acta-cierre/pdf`, {
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName || `Acta_Cierre_Eleccion_${electionId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

export const auditService = {
  getLogs: async (params = {}) => {
    const res = await api.get('/audit/logs', { params });
    return res.data;
  },
};

export default api;
