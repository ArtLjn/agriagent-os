import {create} from 'zustand';
import type {CostRecord, CycleProfit} from '../api/types';
import {costApi} from '../api/client';

interface CostState {
  records: CostRecord[];
  profit: CycleProfit | null;
  loading: boolean;
  error: string | null;
  fetchRecords: (cycleId?: number) => Promise<void>;
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

export const useCostStore = create<CostState>(set => ({
  records: [],
  profit: null,
  loading: false,
  error: null,

  fetchRecords: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await costApi.getRecords(
        cycleId ? {cycle_id: cycleId} : undefined,
      );
      set({records: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  createRecord: async data => {
    set({loading: true, error: null});
    try {
      await costApi.createRecord(data);
      const res = await costApi.getRecords(
        data.cycle_id ? {cycle_id: data.cycle_id} : undefined,
      );
      set({records: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  deleteRecord: async (id, cycleId) => {
    set({loading: true, error: null});
    try {
      await costApi.deleteRecord(id);
      const res = await costApi.getRecords(
        cycleId ? {cycle_id: cycleId} : undefined,
      );
      set({records: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchProfit: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await costApi.getProfit(cycleId);
      set({profit: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  clearError: () => set({error: null}),
}));
