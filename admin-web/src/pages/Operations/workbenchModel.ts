import type { OperationType } from '../../api/operations';

export interface LaborAmount {
  payable: number;
  unpaid: number;
}

export interface OperationOption {
  value: string;
  label: string;
}

type RequestValue = string | number | boolean | null | undefined | unknown[] | Record<string, unknown>;

export function calculateLaborAmount(quantity?: number | null, unitPrice?: number | null, paidAmount?: number | null): LaborAmount {
  const payable = Number(((quantity ?? 0) * (unitPrice ?? 0)).toFixed(2));
  const unpaid = Number(Math.max(payable - (paidAmount ?? 0), 0).toFixed(2));
  return { payable, unpaid };
}

export function normalizeOperationOptions(items: OperationType[]): OperationOption[] {
  return [...items]
    .sort((a, b) => {
      if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
      if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
      return a.name.localeCompare(b.name, 'zh-CN');
    })
    .map((item) => ({
      value: item.name,
      label: `${item.name} · ${item.crop || (item.is_builtin ? '通用' : '自定义')}`,
    }));
}

export function buildRequestBody<T extends Record<string, RequestValue>>(values: T): Partial<T> {
  const entries = Object.entries(values).filter(([, value]) => {
    if (value === null || value === undefined) return false;
    if (typeof value === 'string') return value.trim().length > 0;
    return true;
  });
  return Object.fromEntries(entries) as Partial<T>;
}

export function formatMoney(value?: string | number | null): string {
  const amount = Number(value ?? 0);
  return `¥ ${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function createClientRequestId(prefix = 'admin-web'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
