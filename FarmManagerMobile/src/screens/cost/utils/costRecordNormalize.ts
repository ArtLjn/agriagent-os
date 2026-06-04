import type { CostRecord } from "../../../api/types";

export function normalizeCostRecords(
  records: CostRecord[],
  fallbackCreatedAt?: string
): CostRecord[] {
  const today = new Date().toISOString().split("T")[0];
  return records.map((record) => {
    if (record.created_at || record.createdAt || record.record_date !== today) {
      return record;
    }
    return {
      ...record,
      created_at: fallbackCreatedAt ?? new Date().toISOString(),
    };
  });
}
