export interface CostCategory {
  id: number;
  name: string;
  category_type: 'expense' | 'income';
  is_system: boolean;
}

export interface CategoryCreateParams {
  name: string;
  category_type: 'expense' | 'income';
}
