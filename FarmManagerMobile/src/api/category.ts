import {apiClient} from './client';
import type {CostCategory, CategoryCreateParams} from '../types/category';

export const categoryApi = {
  getCategories: () => apiClient.get<CostCategory[]>('/costs/categories'),
  createCategory: (data: CategoryCreateParams) =>
    apiClient.post<CostCategory>('/costs/categories', data),
  deleteCategory: (id: number) => apiClient.delete(`/costs/categories/${id}`),
};
