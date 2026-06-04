import { create } from 'zustand';
import type { CostRecord, CycleProfit } from '../api/types';
import { costApi } from '../api/client';
import { normalizeCostRecords } from '../screens/cost/utils/costRecordNormalize';

export interface CostRecordFilters {
  cycle_id?: number;
  category?: string;
  source_type?: string;
  source_id?: number;
}

function getRecordList(data: any): CostRecord[] {
  return data?.items ?? data;
}

interface CostState {
  records: CostRecord[];
  profit: CycleProfit | null;
  loading: boolean;
  error: string | null;
  fetchRecords: (filters?: number | CostRecordFilters) => Promise<void>;
  createRecord: (data: {
    cycle_id?: number;
    record_type: string;
    category: string;
    amount: string;
    record_date: string;
    note?: string;
  }) => Promise<void>;
  deleteRecord: (id: number, cycleId?: number) => Promise<void>;
  fetchProfit: (cycleId: number) => Promise<void>;
  clearError: () => void;
}

export const useCostStore = create<CostState>((set) => ({
  records: [],
  profit: null,
  loading: false,
  error: null,

  fetchRecords: async (filters) => {
    set({ loading: true, error: null });
    try {
      const params =
        typeof filters === "number" ? { cycle_id: filters } : filters;
      const res = await costApi.getRecords(params);
      set({
        records: normalizeCostRecords(getRecordList(res.data)),
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createRecord: async (data) => {
    set({ loading: true, error: null });
    try {
      const createdAt = new Date().toISOString();
      await costApi.createRecord(data);
      const res = await costApi.getRecords(
        data.cycle_id ? { cycle_id: data.cycle_id } : undefined
      );
      set({
        records: normalizeCostRecords(getRecordList(res.data), createdAt),
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  deleteRecord: async (id, cycleId) => {
    set({ loading: true, error: null });
    try {
      await costApi.deleteRecord(id);
      const res = await costApi.getRecords(
        cycleId ? { cycle_id: cycleId } : undefined
      );
      set({
        records: normalizeCostRecords(getRecordList(res.data)),
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchProfit: async (cycleId) => {
    set({ loading: true, error: null });
    try {
      const res = await costApi.getProfit(cycleId);
      set({ profit: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
