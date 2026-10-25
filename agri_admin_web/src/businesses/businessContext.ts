import { createContext, useContext } from 'react';
import type { BusinessRuntimeItem } from '../api/businesses';
import { businessViews } from './registry';
import type { BusinessView } from './registry';

const STORAGE_KEY = 'tianzhanggui-business-view';
const defaultView = businessViews[0] ?? null;

export interface BusinessContextValue {
  views: BusinessView[];
  selectedName: string | null;
  selectedView: BusinessView | null;
  runtimeItems: BusinessRuntimeItem[];
  runtimeActive: string | null;
  loading: boolean;
  switchingName: string | null;
  error: string | null;
  selectBusiness: (name: string) => Promise<boolean>;
  refresh: () => void;
  runtimeFor: (name: string) => BusinessRuntimeItem | undefined;
}

const defaultValue: BusinessContextValue = {
  views: businessViews,
  selectedName: defaultView?.name ?? null,
  selectedView: defaultView,
  runtimeItems: [],
  runtimeActive: null,
  loading: false,
  switchingName: null,
  error: null,
  selectBusiness: async () => false,
  refresh: () => {},
  runtimeFor: () => undefined,
};

export const BusinessContext = createContext<BusinessContextValue>(defaultValue);

export function useBusinesses(): BusinessContextValue {
  return useContext(BusinessContext);
}

export function readStoredBusinessView(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function storeBusinessView(name: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, name);
  } catch {
    // 隐私模式下存储不可用时仅本次会话生效
  }
}
