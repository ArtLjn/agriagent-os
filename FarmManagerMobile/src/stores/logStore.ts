import {create} from 'zustand';
import type {FarmLog} from '../api/types';
import {logApi} from '../api/client';

interface LogState {
  logs: FarmLog[];
  loading: boolean;
  error: string | null;
  fetchLogs: (cycleId?: number) => Promise<void>;
  createLog: (data: {
    cycle_id: number;
    operation_type: string;
    operation_date: string;
    note?: string;
  }) => Promise<void>;
  clearError: () => void;
}

export const useLogStore = create<LogState>(set => ({
  logs: [],
  loading: false,
  error: null,

  fetchLogs: async cycleId => {
    set({loading: true, error: null});
    try {
      const res = await logApi.getLogs(
        cycleId ? {cycle_id: cycleId} : undefined,
      );
      set({logs: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  createLog: async data => {
    set({loading: true, error: null});
    try {
      await logApi.createLog(data);
      const res = await logApi.getLogs(
        data.cycle_id ? {cycle_id: data.cycle_id} : undefined,
      );
      set({logs: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  clearError: () => set({error: null}),
}));
