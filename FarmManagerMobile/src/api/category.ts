import { apiClient } from './client';
import type { CostCategory, CategoryCreateParams } from '../types/category';

export const categoryApi = {
  getCategories: () => apiClient.get<CostCategory[]>('/cost-categories'),
  createCategory: (data: CategoryCreateParams) =>
    apiClient.post<CostCategory>('/cost-categories', data),
  deleteCategory: (id: number) => apiClient.delete(`/cost-categories/${id}`),
};
