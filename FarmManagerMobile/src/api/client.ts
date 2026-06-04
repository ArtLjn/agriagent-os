import SSE from "react-native-sse";
import axios from "axios";
import type {
  PendingAction,
  CostRecord,
  DebtListResponse,
  CropTemplateParseResponse,
  CreateTemplateRequest,
  CycleParseResponse,
  ReportResponse,
  ReportListResponse,
  PlantingUnit,
  OperationType,
  Worker,
  OperationWorkOrder,
  LaborEntryCreate,
  WageCreateRequest,
  WageEntryResponse,
  WorkerSummaryResponse,
  UnsettledLaborSummary,
  ConversationListItem,
  ConversationMessageItem,
} from "./types";

const API_BASE_URL = "http://47.98.253.236:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(async (config) => {
  const today = new Date().toISOString().split("T")[0];
  config.headers["X-Current-Date"] = today;
  const { useAuthStore } = require("../stores/authStore");
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      if (error.response.status === 401) {
        const { useAuthStore } = require("../stores/authStore");
        const store = useAuthStore.getState();
        if (store.isLoggedIn) {
          store.logout();
          const { triggerUnauthorized } = require("../stores/authStore");
          triggerUnauthorized();
        }
        return Promise.reject(new Error("登录已过期，请重新登录"));
      }
      const detail = error.response.data?.detail;
      let msg: string;
      if (Array.isArray(detail)) {
        msg = detail
          .map((d: any) => d.msg || d.message || String(d))
          .join("；");
      } else if (typeof detail === "string") {
        msg = detail;
      } else if (detail && typeof detail === "object") {
        msg = detail.msg || detail.message || JSON.stringify(detail);
      } else {
        msg = `请求失败: ${error.response.status}`;
      }
      return Promise.reject(new Error(msg));
    }
    if (error.request) {
      return Promise.reject(new Error("网络连接失败，请检查后重试"));
    }
    return Promise.reject(new Error("请求发生错误"));
  }
);

// 作物模板
export const cropApi = {
  getTemplates: () => apiClient.get("/crops/templates"),
  getTemplate: (id: number) => apiClient.get(`/crops/templates/${id}`),
  parseTemplate: (description: string) => {
    const idempotencyKey = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
      }
    );
    return apiClient.post<CropTemplateParseResponse>(
      "/crops/templates/parse",
      { description },
      {
        headers: { "X-Idempotency-Key": idempotencyKey },
      }
    );
  },
  createTemplate: (data: CreateTemplateRequest) =>
    apiClient.post("/crops/templates", data),
  deleteTemplate: (id: number) => apiClient.delete(`/crops/templates/${id}`),
};

// 种植周期
export const cycleApi = {
  getCycles: () => apiClient.get("/cycles"),
  getCycle: (id: number) => apiClient.get(`/cycles/${id}`),
  createCycle: (data: {
    name: string;
    crop_template_id: number;
    start_date: string;
    field_name?: string;
    total_area_mu?: string;
    season?: string;
    batch_note?: string;
  }) => apiClient.post("/cycles", data),
  deleteCycle: (id: number) => apiClient.delete(`/cycles/${id}`),
  parseCycle: (description: string) => {
    const idempotencyKey = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
      }
    );
    return apiClient.post<CycleParseResponse>(
      "/cycles/parse",
      { description },
      {
        headers: { "X-Idempotency-Key": idempotencyKey },
      }
    );
  },
};

// 种植批次 MVP：种植单元、作业类型、作业单
export const plantingApi = {
  getUnits: (cycleId?: number) =>
    apiClient.get<PlantingUnit[]>("/planting/units", {
      params: cycleId ? { cycle_id: cycleId } : undefined,
    }),
  createUnit: (data: {
    cycle_id: number;
    name: string;
    area_mu?: string;
    planted_date?: string;
    note?: string;
  }) => apiClient.post<PlantingUnit>("/planting/units", data),
  updateUnit: (
    id: number,
    data: {
      name?: string;
      area_mu?: string;
      planted_date?: string;
      note?: string;
      status?: string;
    }
  ) => apiClient.put<PlantingUnit>(`/planting/units/${id}`, data),
  getOperationTypes: (cropName?: string) =>
    apiClient.get<OperationType[]>("/planting/operation-types", {
      params: cropName ? { crop_name: cropName } : undefined,
    }),
  getWorkers: () => apiClient.get<Worker[]>("/planting/workers"),
  getWorkerSummary: () =>
    apiClient.get<WorkerSummaryResponse>("/planting/workers/summary"),
  createWorker: (data: {
    name: string;
    default_pay_type?: string;
    default_unit_price?: string;
  }) => apiClient.post<Worker>("/planting/workers", data),
  createWage: (data: WageCreateRequest) =>
    apiClient.post<WageEntryResponse>("/planting/labor/wages", data),
  getUnsettledLaborSummary: () =>
    apiClient.get<UnsettledLaborSummary>("/planting/labor/unsettled-summary"),
  createWorkOrder: (data: {
    cycle_id: number;
    operation_type: string;
    operation_date: string;
    scope_type: string;
    unit_ids?: number[];
    note?: string;
    labor_entries?: LaborEntryCreate[];
  }) => apiClient.post<OperationWorkOrder>("/planting/work-orders", data),
};

// 农事日志
export const logApi = {
  getLogs: (params?: { cycle_id?: number; operation_type?: string }) =>
    apiClient.get("/logs", { params }),
  createLog: (data: {
    cycle_id: number;
    operation_type: string;
    operation_date: string;
    note?: string;
  }) => apiClient.post("/logs", data),
};

// 成本记账
export const costApi = {
  getRecords: (params?: {
    cycle_id?: number;
    category?: string;
    source_type?: string;
    source_id?: number;
  }) => apiClient.get("/costs", { params }),
  createRecord: (data: {
    cycle_id?: number;
    record_type: string;
    category: string;
    amount: string;
    record_date: string;
    note?: string;
  }) => apiClient.post("/costs", data),
  deleteRecord: (id: number) => apiClient.delete(`/costs/${id}`),
  getProfit: (cycleId: number) =>
    apiClient.get(`/costs/cycles/${cycleId}/profit`),
  getYearlySummary: (year: number) => apiClient.get(`/costs/summary/${year}`),
  parseRecord: (description: string) => {
    const idempotencyKey = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
      }
    );
    return apiClient.post(
      "/costs/parse",
      { description },
      {
        headers: { "X-Idempotency-Key": idempotencyKey },
      }
    );
  },
};

// Agent
export const agentApi = {
  chat: (data: { cycle_id?: number; message: string }) =>
    apiClient.post("/agent/chat", data),
  streamChat: (
    data: { cycle_id?: number; message: string; session_id?: string },
    onChunk: (chunk: string) => void,
    onDone: () => void,
    onError: (err: string) => void,
    onPendingAction?: (action: PendingAction) => void
  ) => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const { useAuthStore } = require("../stores/authStore");
    const token = useAuthStore.getState().token;
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    const es = new SSE(`${API_BASE_URL}/agent/chat/stream`, {
      headers,
      method: "POST",
      body: JSON.stringify(data),
    });
    es.addEventListener("message", (event) => {
      if (!event.data) {
        return;
      }
      const payload = event.data;
      if (payload === "[DONE]") {
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
        if (parsed.content) {
          onChunk(parsed.content);
        }
        if (parsed.pending_action && onPendingAction) {
          onPendingAction(parsed.pending_action);
        }
      } catch {
        // 忽略非 JSON 行
      }
    });
    es.addEventListener("error", () => {
      es.close();
      onError("网络连接失败，请检查后重试");
    });
    return es;
  },
  getDailyAdvice: (cycleId?: number) =>
    apiClient.get("/agent/daily", { params: { cycle_id: cycleId } }),
  refreshAdvice: (cycleId?: number) =>
    apiClient.post("/agent/daily/refresh", null, {
      params: { cycle_id: cycleId },
    }),
  generateReport: (data: { cycle_id?: number; report_type: string }) =>
    apiClient.post<ReportResponse>("/agent/report", data),
  getAdviceHistory: (cycleId?: number) =>
    apiClient.get("/agent/advice-history", { params: { cycle_id: cycleId } }),
  getReportHistory: (page: number = 1, size: number = 10) =>
    apiClient.get<ReportListResponse>("/agent/reports", {
      params: { page, size },
    }),
  deleteReport: (id: number) => apiClient.delete(`/agent/reports/${id}`),
  getConversations: (limit: number = 20) =>
    apiClient.get<ConversationListItem[]>("/agent/conversations", {
      params: { limit },
    }),
  getConversationMessages: (sessionId: string) =>
    apiClient.get<ConversationMessageItem[]>(
      `/agent/conversations/${encodeURIComponent(sessionId)}/messages`
    ),
};

// 债务管理
export const debtApi = {
  getDebts: (params?: {
    counterparty?: string;
    page?: number;
    size?: number;
  }) => apiClient.get<DebtListResponse>("/debts", { params }),
  createDebt: (data: {
    record_type: string;
    category: string;
    amount: string;
    record_date: string;
    note?: string;
    record_subtype?: string;
    counterparty?: string;
    due_date?: string;
  }) => apiClient.post<CostRecord>("/debts", data),
  settleDebt: (data: {
    counterparty: string;
    amount?: string;
    note?: string;
  }) => apiClient.post<CostRecord>("/debts/settle", data),
};

// 天气
export const weatherApi = {
  getForecast: (
    days: number = 3,
    lat?: number,
    lon?: number,
    location?: string
  ) =>
    apiClient.get("/weather/forecast", {
      params: { days, lat, lon, location },
    }),
};

// 用户设置
export interface SettingsResponse {
  display_name: string;
  default_city: string | null;
  default_lat: number | null;
  default_lon: number | null;
}

export const settingsApi = {
  get: () => apiClient.get<SettingsResponse>("/settings"),
  update: (data: {
    display_name?: string;
    default_city?: string;
    default_lat?: number;
    default_lon?: number;
  }) => apiClient.put<SettingsResponse>("/settings", data),
};
