export interface CostCategory {
  id: number;
  name: string;
  type: 'cost' | 'income';
  icon: string;
  sort_order: number;
  is_default: boolean;
}

export interface CategoryCreateParams {
  name: string;
  type: 'cost' | 'income';
  icon?: string;
}
