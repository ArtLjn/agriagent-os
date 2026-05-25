import 'react-native-get-random-values';
import { v4 as uuidv4 } from 'uuid';

import SSE from 'react-native-sse';
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
  const today = new Date().toISOString().split('T')[0];
  config.headers['X-Current-Date'] = today;
  return config;
});

apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response) {
      const detail = error.response.data?.detail;
      let msg: string;
      if (Array.isArray(detail)) {
        msg = detail.map((d: any) => d.msg || d.message || String(d)).join('；');
      } else if (typeof detail === 'string') {
        msg = detail;
      } else if (detail && typeof detail === 'object') {
        msg = detail.msg || detail.message || JSON.stringify(detail);
      } else {
        msg = `请求失败: ${error.response.status}`;
      }
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
  parseRecord: (description: string) => {
    const idempotencyKey = uuidv4();
    return apiClient.post('/costs/parse', { description }, {
      headers: { 'X-Idempotency-Key': idempotencyKey },
    });
  },
};

// Agent
export const agentApi = {
  chat: (data: { cycle_id?: number; message: string }) => apiClient.post('/agent/chat', data),
  streamChat: (
    data: { cycle_id?: number; message: string },
    onChunk: (chunk: string) => void,
    onDone: () => void,
    onError: (err: string) => void,
  ) => {
    const es = new SSE(`${API_BASE_URL}/agent/chat/stream`, {
      headers: {'Content-Type': 'application/json'},
      method: 'POST',
      body: JSON.stringify(data),
    });
    es.addEventListener('message', event => {
      if (!event.data) return;
      const payload = event.data;
      if (payload === '[DONE]') {
        es.close();
        onDone();
        return;
      }
      try {
        const parsed = JSON.parse(payload);
        if (parsed.error) {
          es.close();
          onError(parsed.error);
          return;
        }
        if (parsed.content) onChunk(parsed.content);
      } catch {
        // 忽略非 JSON 行
      }
    });
    es.addEventListener('error', () => {
      es.close();
      onError('网络连接失败，请检查后重试');
    });
    return es;
  },
  getDailyAdvice: (cycleId?: number) =>
    apiClient.get('/agent/daily', { params: { cycle_id: cycleId } }),
  refreshAdvice: (cycleId?: number) =>
    apiClient.post('/agent/daily/refresh', null, { params: { cycle_id: cycleId } }),
  generateReport: (data: { cycle_id?: number; report_type: string }) =>
    apiClient.post('/agent/report', data),
  getAdviceHistory: (cycleId?: number) =>
    apiClient.get('/agent/advice-history', { params: { cycle_id: cycleId } }),
  getReportHistory: (page: number = 1, size: number = 10) =>
    apiClient.get('/agent/reports', { params: { page, size } }),
};

// 天气
export const weatherApi = {
  getForecast: (days: number = 3, lat?: number, lon?: number) =>
    apiClient.get('/weather/forecast', { params: { days, lat, lon } }),
};
