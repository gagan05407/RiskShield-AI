import axios from 'axios';

const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL;
  if (!envUrl) return 'http://localhost:8000/api';
  const cleanUrl = envUrl.replace(/\/+$/, '');
  return cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
};

const API_BASE = getApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add Authorization token header
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('riskshield_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle token expiry / 401 Unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Don't auto-redirect on failed login attempt itself
      if (!error.config.url.includes('/auth/login')) {
        localStorage.removeItem('riskshield_token');
        localStorage.removeItem('riskshield_user');
        window.dispatchEvent(new Event('auth_logout'));
      }
    }
    return Promise.reject(error);
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// AUTHENTICATION API CALLS
// ─────────────────────────────────────────────────────────────────────────────

export const loginUser = async (username, password) => {
  const response = await api.post('/auth/login', { username, password });
  if (response.data && response.data.access_token) {
    localStorage.setItem('riskshield_token', response.data.access_token);
    localStorage.setItem('riskshield_user', JSON.stringify(response.data.user));
  }
  return response.data;
};

export const registerUser = async (userData) => {
  const response = await api.post('/auth/register', userData);
  return response.data;
};

export const getCurrentUser = () => api.get('/auth/me').then((r) => r.data);

export const logoutUser = () => {
  localStorage.removeItem('riskshield_token');
  localStorage.removeItem('riskshield_user');
  window.dispatchEvent(new Event('auth_logout'));
};

// ─────────────────────────────────────────────────────────────────────────────
// ADMIN USER APPROVAL API CALLS
// ─────────────────────────────────────────────────────────────────────────────

export const getAdminUsers = () => api.get('/admin/users').then((r) => r.data);
export const approveUser = (userId) => api.post(`/admin/users/${userId}/approve`).then((r) => r.data);
export const rejectUser = (userId) => api.post(`/admin/users/${userId}/reject`).then((r) => r.data);

// ─────────────────────────────────────────────────────────────────────────────
// APPLICATION API CALLS
// ─────────────────────────────────────────────────────────────────────────────

export const getSystemStatus = () => api.get('/system/status').then((r) => r.data);
export const getRedisCeleryStatus = () => api.get('/system/redis-celery-status').then((r) => r.data);
export const getDatasets = () => api.get('/datasets').then((r) => r.data);
export const switchDataset = (filename) => api.post('/dataset/switch', { dataset_filename: filename }).then((r) => r.data);

export const getOverview = () => api.get('/overview').then((r) => r.data);

export const getTransactions = (params) => api.get('/transactions', { params }).then((r) => r.data);
export const getTransactionDetail = (txId) => api.get(`/transactions/${txId}`).then((r) => r.data);
export const createNewTransaction = (data) => api.post('/transactions/new', data).then((r) => r.data);
export const recordAnalystDecision = (txId, decision, remark) => api.post(`/transactions/${txId}/decision`, { decision, remark }).then((r) => r.data);
export const recordDecision = recordAnalystDecision;

export const uploadTransactionsCsv = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/transactions/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then((r) => r.data);
};

export const getExportUrl = (exportType) => `${API_BASE}/export/${exportType}`;

export const runInvestigation = (txId) => api.post('/investigation/run', { transaction_id: txId }).then((r) => r.data);

export const getModelPerformance = () => api.get('/model-performance').then((r) => r.data);
export const calculateCustomCost = (data) => api.post('/model-performance/cost', data).then((r) => r.data);
export const getRiskThreshold = () => api.get('/model-performance/threshold').then((r) => r.data);
export const updateRiskThreshold = (threshold) => api.post('/model-performance/threshold', { threshold }).then((r) => r.data);


export const getAuditLogs = () => api.get('/audit-logs').then((r) => r.data);

export const getAIConfig = () => api.get('/ai/config').then((r) => r.data);
export const getAIModels = (provider) => api.get('/ai/models', { params: { provider } }).then((r) => r.data);
export const saveAIConfig = (data) => api.post('/ai/config', data).then((r) => r.data);
export const testAIConfig = (data) => api.post('/ai/test', data).then((r) => r.data);

export const sendCopilotMessage = (userQuery, targetTxId) => api.post('/copilot', { user_query: userQuery, target_tx_id: targetTxId }).then((r) => r.data);

// Communication API Calls
export const getAdminConversations = () => api.get('/communication/conversations').then((r) => r.data);
export const getConversationMessages = (analystId) => api.get('/communication/conversation', { params: analystId ? { analyst_id: analystId } : {} }).then((r) => r.data);
export const sendCommunicationMessage = (data) => api.post('/communication/send', data).then((r) => r.data);
export const notifyApiKeyRequest = () => api.post('/communication/notify-api-key').then((r) => r.data);
export const resolveApiKeyRequest = (messageId) => api.post('/communication/resolve-request', { message_id: messageId }).then((r) => r.data);
export const getUnreadNotificationCount = () => api.get('/communication/unread-count').then((r) => r.data);

