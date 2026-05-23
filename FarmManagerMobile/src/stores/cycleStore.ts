import {create} from 'zustand';
import type {CropCycle, CropCycleListItem, CropTemplate} from '../api/types';
import {cycleApi, cropApi} from '../api/client';

interface CycleState {
  cycles: CropCycleListItem[];
  currentCycle: CropCycle | null;
  templates: CropTemplate[];
  loading: boolean;
  error: string | null;
  fetchCycles: () => Promise<void>;
  fetchCycleDetail: (id: number) => Promise<void>;
  fetchTemplates: () => Promise<void>;
  createCycle: (data: {
    name: string;
    crop_template_id: number;
    start_date: string;
    field_name?: string;
  }) => Promise<void>;
  clearError: () => void;
}

export const useCycleStore = create<CycleState>(set => ({
  cycles: [],
  currentCycle: null,
  templates: [],
  loading: false,
  error: null,

  fetchCycles: async () => {
    set({loading: true, error: null});
    try {
      const res = await cycleApi.getCycles();
      set({cycles: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchCycleDetail: async (id: number) => {
    set({loading: true, error: null});
    try {
      const res = await cycleApi.getCycle(id);
      set({currentCycle: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  fetchTemplates: async () => {
    set({loading: true, error: null});
    try {
      const res = await cropApi.getTemplates();
      set({templates: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  createCycle: async data => {
    set({loading: true, error: null});
    try {
      await cycleApi.createCycle(data);
      const res = await cycleApi.getCycles();
      set({cycles: res.data, loading: false});
    } catch (err: any) {
      set({error: err.message, loading: false});
    }
  },

  clearError: () => set({error: null}),
}));
