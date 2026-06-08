import dayjs from 'dayjs';
import type { CostParseResponse } from '../../api/costs';

export interface CostFormValues {
  record_type: string;
  category: string;
  amount: number;
  record_date: dayjs.Dayjs;
  note?: string;
}

export function buildCostFormValues(parsed: CostParseResponse): CostFormValues {
  return {
    record_type: parsed.record_type,
    category: parsed.category,
    amount: Number(parsed.amount),
    record_date: dayjs(parsed.record_date),
    note: parsed.note ?? undefined,
  };
}
