import dayjs from "dayjs";
import type { CostRecord } from "../../../api/types";

export type RecordFilterType = "all" | "cost" | "income" | "debt";
export type DateRangeFilter = "today" | "week" | "month";

interface FilterOptions {
  query: string;
  type: RecordFilterType;
  dateRange: DateRangeFilter;
  month: string;
  now?: string;
  category?: string | null;
}

function toAmountNumber(amount: string): number {
  const parsed = Number(String(amount).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatRecordAmount(amount: string): string {
  const value = toAmountNumber(amount);
  const abs = Math.abs(value);

  if (abs >= 100000) {
    return `¥${(value / 10000).toFixed(1)}万`;
  }

  return `¥${new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value)}`;
}

export function formatRecordTimestamp(
  record: CostRecord,
  nowInput?: string
): string {
  const now = nowInput ? dayjs(nowInput) : dayjs();
  const recordDay = dayjs(record.record_date);
  const createdAt = record.created_at ? dayjs(record.created_at) : null;
  const timeText = createdAt?.isValid() ? createdAt.format("HH:mm") : "--:--";

  if (recordDay.isSame(now, "day")) {
    return `今天 ${timeText}`;
  }
  if (recordDay.isSame(now.subtract(1, "day"), "day")) {
    return `昨天 ${timeText}`;
  }
  if (recordDay.year() === now.year()) {
    return `${recordDay.format("M月D日")} ${timeText}`;
  }
  return `${recordDay.format("YYYY年M月D日")} ${timeText}`;
}

export function getRecordTimeText(record: CostRecord): string {
  if (!record.created_at) {
    return "--:--";
  }
  const createdAt = dayjs(record.created_at);
  return createdAt.isValid() ? createdAt.format("HH:mm") : "--:--";
}

function isDebtRecord(record: CostRecord): boolean {
  return Boolean(
    record.record_subtype ||
      record.counterparty ||
      (record as CostRecord & { payment_method?: string }).payment_method ===
        "debt"
  );
}

function matchesDateRange(
  record: CostRecord,
  options: Pick<FilterOptions, "dateRange" | "month" | "now">
): boolean {
  const recordDay = dayjs(record.record_date);
  const now = options.now ? dayjs(options.now) : dayjs();

  if (options.dateRange === "today") {
    return recordDay.isSame(now, "day");
  }
  if (options.dateRange === "week") {
    return recordDay.isAfter(now.subtract(7, "day"), "day");
  }
  return record.record_date.startsWith(options.month);
}

function matchesQuery(record: CostRecord, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }

  const paymentMethod = (record as CostRecord & { payment_method?: string })
    .payment_method;
  return [
    record.category,
    record.note,
    record.counterparty,
    record.amount,
    paymentMethod,
  ]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(normalized));
}

export function filterCostRecords(
  records: CostRecord[],
  options: FilterOptions
): CostRecord[] {
  return records.filter((record) => {
    if (!matchesDateRange(record, options)) {
      return false;
    }
    if (options.type === "debt" && !isDebtRecord(record)) {
      return false;
    }
    if (
      options.type !== "all" &&
      options.type !== "debt" &&
      record.record_type !== options.type
    ) {
      return false;
    }
    if (options.category && record.category !== options.category) {
      return false;
    }
    return matchesQuery(record, options.query);
  });
}
