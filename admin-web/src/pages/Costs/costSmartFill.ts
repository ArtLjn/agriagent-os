import dayjs from 'dayjs';
import type { CostParseResponse } from '../../api/costs';

export interface CostFormValues {
  record_type: string;
  category: string;
  amount: number;
  record_date: dayjs.Dayjs;
  note?: string;
  record_subtype?: string;
  counterparty?: string;
  due_date?: dayjs.Dayjs;
}

export function buildCostFormValues(parsed: CostParseResponse): CostFormValues {
  return {
    record_type: parsed.record_type,
    category: parsed.category,
    amount: Number(parsed.amount),
    record_date: dayjs(parsed.record_date),
    note: parsed.note ?? undefined,
    record_subtype: parsed.record_subtype ?? undefined,
    counterparty: parsed.counterparty ?? undefined,
    due_date: parsed.due_date ? dayjs(parsed.due_date) : undefined,
  };
}

export function buildCostCreatePayload(
  values: CostFormValues,
  cycleId?: number,
) {
  return {
    record_type: values.record_type,
    category: values.category,
    amount: String(values.amount),
    record_date: values.record_date.format('YYYY-MM-DD'),
    note: values.note,
    record_subtype: values.record_subtype,
    counterparty: values.counterparty,
    due_date: values.due_date?.format('YYYY-MM-DD'),
    cycle_id: cycleId,
  };
}
