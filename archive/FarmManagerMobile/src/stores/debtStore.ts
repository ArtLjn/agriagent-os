import { create } from 'zustand';
import type { CostRecord, DebtSummary } from '../api/types';
import { debtApi } from '../api/client';

interface DebtState {
  debts: CostRecord[];
  summary: DebtSummary[];
  total: number;
  loading: boolean;
  error: string | null;
  fetchDebts: (counterparty?: string) => Promise<void>;
  createDebt: (data: {
    record_type: string;
    category: string;
    amount: string;
    record_date: string;
    note?: string;
    record_subtype?: string;
    counterparty?: string;
    due_date?: string;
  }) => Promise<void>;
  settleDebt: (
    counterparty: string,
    amount?: string,
    note?: string
  ) => Promise<void>;
  clearError: () => void;
}

export const useDebtStore = create<DebtState>((set) => ({
  debts: [],
  summary: [],
  total: 0,
  loading: false,
  error: null,

  fetchDebts: async (counterparty) => {
    set({ loading: true, error: null });
    try {
      const res = await debtApi.getDebts({ counterparty, page: 1, size: 100 });
      const data = res.data;
      set({
        debts: data.items,
        summary: data.summary,
        total: data.total,
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createDebt: async (data) => {
    set({ loading: true, error: null });
    try {
      await debtApi.createDebt(data);
      const res = await debtApi.getDebts({ page: 1, size: 100 });
      const d = res.data;
      set({
        debts: d.items,
        summary: d.summary,
        total: d.total,
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  settleDebt: async (counterparty, amount, note) => {
    set({ loading: true, error: null });
    try {
      await debtApi.settleDebt({ counterparty, amount, note });
      const res = await debtApi.getDebts({ page: 1, size: 100 });
      const d = res.data;
      set({
        debts: d.items,
        summary: d.summary,
        total: d.total,
        loading: false,
      });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
