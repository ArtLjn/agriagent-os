import { create } from 'zustand';
import type { CropCycle, CropCycleListItem, CropTemplate, OperationType, PlantingUnit } from '../api/types';
import { cycleApi, cropApi, plantingApi } from '../api/client';

interface CycleState {
  cycles: CropCycleListItem[];
  currentCycle: CropCycle | null;
  templates: CropTemplate[];
  units: PlantingUnit[];
  operationTypes: OperationType[];
  loading: boolean;
  error: string | null;
  fetchCycles: () => Promise<void>;
  fetchCycleDetail: (id: number) => Promise<void>;
  fetchTemplates: () => Promise<void>;
  fetchUnits: (cycleId: number) => Promise<void>;
  fetchOperationTypes: (cropName?: string) => Promise<void>;
  createCycle: (data: {
    name: string;
    crop_template_id: number;
    start_date: string;
    field_name?: string;
    total_area_mu?: string;
    season?: string;
    batch_note?: string;
  }) => Promise<void>;
  deleteCycles: (ids: number[]) => Promise<void>;
  clearError: () => void;
}

export const useCycleStore = create<CycleState>((set) => ({
  cycles: [],
  currentCycle: null,
  templates: [],
  units: [],
  operationTypes: [],
  loading: false,
  error: null,

  fetchCycles: async () => {
    set({ loading: true, error: null });
    try {
      const res = await cycleApi.getCycles();
      const data = (res.data as any)?.items ?? res.data;
      set({ cycles: data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchCycleDetail: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const res = await cycleApi.getCycle(id);
      set({ currentCycle: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchTemplates: async () => {
    set({ loading: true, error: null });
    try {
      const res = await cropApi.getTemplates();
      const tData = (res.data as any)?.items ?? res.data;
      set({ templates: tData, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  fetchUnits: async (cycleId) => {
    try {
      const res = await plantingApi.getUnits(cycleId);
      set({ units: res.data });
    } catch (err: any) {
      set({ error: err.message });
    }
  },

  fetchOperationTypes: async (cropName) => {
    try {
      const res = await plantingApi.getOperationTypes(cropName);
      set({ operationTypes: res.data });
    } catch (err: any) {
      set({ error: err.message });
    }
  },

  createCycle: async (data) => {
    set({ loading: true, error: null });
    try {
      await cycleApi.createCycle(data);
      const res2 = await cycleApi.getCycles();
      const items = (res2.data as any)?.items ?? res2.data;
      set({ cycles: items, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  deleteCycles: async (ids) => {
    set({ loading: true, error: null });
    try {
      await Promise.all(ids.map((id) => cycleApi.deleteCycle(id)));
      const res = await cycleApi.getCycles();
      const items = (res.data as any)?.items ?? res.data;
      set({ cycles: items, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
      throw err;
    }
  },

  clearError: () => set({ error: null }),
}));
