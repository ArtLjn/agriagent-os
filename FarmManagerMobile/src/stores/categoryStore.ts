import { create } from 'zustand';
import type { CostCategory, CategoryCreateParams } from '../types/category';
import { categoryApi } from '../api/category';

interface CategoryState {
  categories: CostCategory[];
  loading: boolean;
  error: string | null;
  fetchCategories: () => Promise<void>;
  createCategory: (data: CategoryCreateParams) => Promise<void>;
  deleteCategory: (id: number) => Promise<void>;
  clearError: () => void;
}

export const useCategoryStore = create<CategoryState>((set) => ({
  categories: [],
  loading: false,
  error: null,

  fetchCategories: async () => {
    set({ loading: true, error: null });
    try {
      const res = await categoryApi.getCategories();
      set({ categories: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  createCategory: async (data) => {
    set({ loading: true, error: null });
    try {
      await categoryApi.createCategory(data);
      const res = await categoryApi.getCategories();
      set({ categories: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  deleteCategory: async (id) => {
    set({ loading: true, error: null });
    try {
      await categoryApi.deleteCategory(id);
      const res = await categoryApi.getCategories();
      set({ categories: res.data, loading: false });
    } catch (err: any) {
      set({ error: err.message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
