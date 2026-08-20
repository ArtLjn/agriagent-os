import apiClient from './client';
import type { CostRecord } from './costs';

export interface PaginatedList<T> {
  items: T[];
  total: number;
}

export interface PlantingUnit {
  id: number;
  farm_id: number;
  cycle_id: number;
  name: string;
  area_mu?: string | number | null;
  planted_date?: string | null;
  status: string;
  note?: string | null;
  created_at?: string | null;
}

export interface Worker {
  id: number;
  farm_id: number;
  name: string;
  phone?: string | null;
  default_pay_type: string;
  default_unit_price?: string | number | null;
  note?: string | null;
  status: string;
  created_at?: string | null;
}

export interface WorkerLaborSummary extends Worker {
  total_payable: string | number;
  total_paid: string | number;
  total_unpaid: string | number;
  entry_count: number;
  cycle_summaries: Array<{
    cycle_id?: number | null;
    cycle_name?: string | null;
    total_payable: string | number;
    total_paid: string | number;
    total_unpaid: string | number;
    entry_count: number;
  }>;
}

export interface OperationType {
  name: string;
  crop?: string | null;
  is_builtin: boolean;
  sort_order: number;
}

export interface LaborEntryPayload {
  worker_id: number;
  pay_type: string;
  quantity: string | number;
  unit_price: string | number;
  paid_amount?: string | number;
  note?: string;
}

export interface OperationWorkOrder {
  id: number;
  farm_id: number;
  cycle_id?: number | null;
  cycle_name?: string | null;
  operation_type: string;
  operation_date: string;
  scope_type: string;
  unit_ids: number[];
  unit_names: string[];
  note?: string | null;
  photo_urls?: string | null;
  labor_entries: Array<{
    id: number;
    worker_id: number;
    worker_name?: string | null;
    pay_type: string;
    quantity: string | number;
    unit_price: string | number;
    payable_amount: string | number;
    paid_amount: string | number;
    unpaid_amount: string | number;
    settlement_status: string;
    note?: string | null;
  }>;
  total_payable_amount: string | number;
  total_paid_amount: string | number;
  total_unpaid_amount: string | number;
  labor_cost_record_id?: number | null;
  created_at?: string | null;
}

export interface RecentOperation {
  source_type: string;
  source_id: number;
  cycle_id?: number | null;
  cycle_name?: string | null;
  operation_type: string;
  operation_date: string;
  scope_text?: string | null;
  note?: string | null;
}

export interface WagePayload {
  cycle_id: number;
  operation_type: string;
  worker_id?: number | null;
  worker_name?: string;
  crop_name?: string;
  pay_type: string;
  quantity: string | number;
  unit_price: string | number;
  paid_amount: string | number;
  note?: string;
  work_date: string;
  client_request_id: string;
}

export interface DebtListResponse {
  items: CostRecord[];
  total: number;
  summary: Array<{
    counterparty: string;
    total_debt: string | number;
    total_settled: string | number;
    remaining: string | number;
    record_count: number;
  }>;
}

export interface CostCategory {
  id: number;
  farm_id: number;
  name: string;
  type: 'cost' | 'income';
  icon: string;
  sort_order: number;
  is_default: boolean;
}

export const operationsApi = {
  listUnits: async (cycleId?: number): Promise<PlantingUnit[]> => {
    const res = await apiClient.get<PaginatedList<PlantingUnit>>('/planting-units', { params: { cycle_id: cycleId } });
    return res.data.items;
  },
  createUnit: (data: Omit<PlantingUnit, 'id' | 'farm_id' | 'created_at'>) =>
    apiClient.post<PlantingUnit>('/planting-units', data),
  updateUnit: (unitId: number, data: Partial<PlantingUnit>) =>
    apiClient.put<PlantingUnit>(`/planting-units/${unitId}`, data),
  deleteUnit: (unitId: number) =>
    apiClient.delete<{ deleted: number }>(`/planting-units/${unitId}`),

  listWorkers: async (activeOnly = false): Promise<Worker[]> => {
    const res = await apiClient.get<PaginatedList<Worker>>('/workers', { params: { active_only: activeOnly } });
    return res.data.items;
  },
  listWorkerSummaries: (activeOnly = false) =>
    apiClient.get<PaginatedList<WorkerLaborSummary>>('/workers/summary', { params: { active_only: activeOnly } }),
  createWorker: (data: Omit<Worker, 'id' | 'farm_id' | 'created_at'>) =>
    apiClient.post<Worker>('/workers', data),
  updateWorker: (workerId: number, data: Partial<Worker>) =>
    apiClient.put<Worker>(`/workers/${workerId}`, data),
  deleteWorker: (workerId: number) =>
    apiClient.delete<{ deleted: number }>(`/workers/${workerId}`),

  listOperationTypes: async (cropName?: string): Promise<OperationType[]> => {
    const res = await apiClient.get<{ items: OperationType[] }>('/operation-types', { params: { crop_name: cropName } });
    return res.data.items;
  },
  listWorkOrders: (params?: { cycle_id?: number; page?: number; page_size?: number }) =>
    apiClient.get<PaginatedList<OperationWorkOrder>>('/work-orders', { params }),
  getWorkOrder: (workOrderId: number) =>
    apiClient.get<OperationWorkOrder>(`/work-orders/${workOrderId}`),
  createWorkOrder: (data: {
    cycle_id?: number | null;
    operation_type: string;
    operation_date: string;
    scope_type: string;
    unit_ids: number[];
    note?: string;
    photo_urls?: string;
    labor_entries: LaborEntryPayload[];
  }) => apiClient.post<OperationWorkOrder>('/work-orders', data),
  settleWorkOrderLabor: (workOrderId: number, data?: { amount?: number; worker_name?: string; cycle_id?: number; start_date?: string; end_date?: string }) =>
    apiClient.post<OperationWorkOrder>(`/work-orders/${workOrderId}/settle`, data),
  listRecentOperations: async (params?: { cycle_id?: number; days?: number; limit?: number }): Promise<RecentOperation[]> => {
    const res = await apiClient.get<{ items: RecentOperation[] }>('/recent-operations', { params });
    return res.data.items;
  },
  getUnsettledLaborSummary: () =>
    apiClient.get<Record<string, unknown>>('/labor/unsettled-summary'),
  saveWage: (data: WagePayload) =>
    apiClient.post<OperationWorkOrder['labor_entries'][number] & {
      cycle_id: number;
      operation_type: string;
      worker_name: string;
      cost_record_id?: number | null;
    }>('/labor/wages', data),
  queryWages: (params: { mode: 'unpaid' | 'monthly' | 'worker'; worker_name?: string; month?: string; start_date?: string; end_date?: string }) =>
    apiClient.get<Record<string, unknown>>('/labor/wages', { params }),

  listDebts: (params?: { counterparty?: string; page?: number; page_size?: number }) =>
    apiClient.get<DebtListResponse>('/debts', { params }),
  createDebt: (data: Record<string, unknown>) =>
    apiClient.post<CostRecord>('/debts', data),
  settleDebt: (data: { counterparty: string; amount?: string | number | null; note?: string }) =>
    apiClient.post<CostRecord>('/debts/settle', data),

  listCostCategories: async (): Promise<CostCategory[]> => {
    const res = await apiClient.get<{ items: CostCategory[] }>('/cost-categories');
    return res.data.items;
  },
  createCostCategory: (data: Omit<CostCategory, 'id' | 'farm_id' | 'is_default'>) =>
    apiClient.post<CostCategory>('/cost-categories', data),
  updateCostCategory: (categoryId: number, data: Partial<CostCategory>) =>
    apiClient.put<CostCategory>(`/cost-categories/${categoryId}`, data),
  deleteCostCategory: (categoryId: number) =>
    apiClient.delete<{ deleted: number }>(`/cost-categories/${categoryId}`),

};
