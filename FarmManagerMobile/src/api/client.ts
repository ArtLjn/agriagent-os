import axios from 'axios';

const API_BASE_URL = 'http://10.0.2.2:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use(async config => {
  return config;
});

apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      const msg = error.response.data?.detail || `请求失败: ${error.response.status}`;
      return Promise.reject(new Error(msg));
    }
    if (error.request) {
      return Promise.reject(new Error('网络连接失败，请检查后重试'));
    }
    return Promise.reject(new Error('请求发生错误'));
  },
);

// 作物模板
export const cropApi = {
  getTemplates: () => apiClient.get('/crops/templates'),
  getTemplate: (id: number) => apiClient.get(`/crops/templates/${id}`),
};

// 种植周期
export const cycleApi = {
  getCycles: () => apiClient.get('/cycles'),
  getCycle: (id: number) => apiClient.get(`/cycles/${id}`),
  createCycle: (data: { name: string; crop_template_id: number; start_date: string; field_name?: string }) =>
    apiClient.post('/cycles', data),
};

// 农事日志
export const logApi = {
  getLogs: (params?: { cycle_id?: number; operation_type?: string }) =>
    apiClient.get('/logs', { params }),
  createLog: (data: { cycle_id: number; operation_type: string; operation_date: string; note?: string }) =>
    apiClient.post('/logs', data),
};

// 成本记账
export const costApi = {
  getRecords: (params?: { cycle_id?: number; category?: string }) =>
    apiClient.get('/costs', { params }),
  createRecord: (data: { cycle_id?: number; record_type: string; category: string; amount: string; record_date: string; note?: string }) =>
    apiClient.post('/costs', data),
  deleteRecord: (id: number) => apiClient.delete(`/costs/${id}`),
  getProfit: (cycleId: number) => apiClient.get(`/costs/cycles/${cycleId}/profit`),
  getYearlySummary: (year: number) => apiClient.get(`/costs/summary/${year}`),
  parseRecord: (description: string) =>
    apiClient.post('/costs/parse', { description }),
};

// Agent
export const agentApi = {
  chat: (data: { cycle_id?: number; message: string }) => apiClient.post('/agent/chat', data),
  getDailyAdvice: (cycleId?: number) => apiClient.get('/agent/daily', { params: { cycle_id: cycleId } }),
  generateReport: (data: { cycle_id?: number; report_type: string }) =>
    apiClient.post('/agent/report', data),
  getAdviceHistory: (cycleId?: number) =>
    apiClient.get('/agent/advice-history', { params: { cycle_id: cycleId } }),
  getReportHistory: (cycleId?: number) =>
    apiClient.get('/agent/report-history', { params: { cycle_id: cycleId } }),
};

// 天气
export const weatherApi = {
  getForecast: (days: number = 3, lat?: number, lon?: number) =>
    apiClient.get('/weather/forecast', { params: { days, lat, lon } }),
};
