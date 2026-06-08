import {
  filterCostRecords,
  formatRecordAmount,
  formatRecordTimestamp,
  getRecordNoteText,
  getRecordTimeText,
} from "../recordDisplay";
import type { CostRecord } from "../../../../api/types";

const baseRecord: CostRecord = {
  id: 1,
  cycle_id: null,
  record_type: "cost",
  category: "化肥",
  amount: "120",
  record_date: "2026-06-03",
  note: "老王农资店",
  counterparty: "老王",
  created_at: "2026-06-03T14:32:00",
};

describe("recordDisplay", () => {
  it("格式化超长金额为万单位，避免列表溢出", () => {
    expect(formatRecordAmount("123456.78")).toBe("¥12.3万");
    expect(formatRecordAmount("12345678.9")).toBe("¥1234.6万");
    expect(formatRecordAmount("1234.00")).toBe("¥1,234");
  });

  it("优先显示业务日期和创建时间组合出的具体时间", () => {
    expect(formatRecordTimestamp(baseRecord, "2026-06-03T16:00:00")).toBe(
      "今天 14:32"
    );
    expect(
      formatRecordTimestamp(
        { ...baseRecord, record_date: "2026-06-02" },
        "2026-06-03T16:00:00"
      )
    ).toBe("昨天 14:32");
  });

  it("兼容接口返回的 createdAt 字段并清理空备注占位", () => {
    const record = {
      ...baseRecord,
      created_at: undefined,
      createdAt: "2026-06-03T08:05:00",
      note: "NULL",
    } as CostRecord & { createdAt: string };

    expect(getRecordTimeText(record)).toBe("08:05");
    expect(formatRecordTimestamp(record, "2026-06-03T16:00:00")).toBe(
      "今天 08:05"
    );
    expect(getRecordNoteText(record)).toBeNull();
  });

  it("缺少创建时间时不显示占位符", () => {
    const record = {
      ...baseRecord,
      created_at: undefined,
      createdAt: undefined,
    };

    expect(getRecordTimeText(record)).toBeNull();
    expect(formatRecordTimestamp(record, "2026-06-03T16:00:00")).toBe("今天");
  });

  it("按关键词、类型和快捷时间筛选账单", () => {
    const records: CostRecord[] = [
      baseRecord,
      {
        ...baseRecord,
        id: 2,
        record_type: "income",
        category: "销售",
        amount: "3000",
        note: "卖西瓜",
        record_date: "2026-06-01",
        created_at: "2026-06-01T09:10:00",
      },
      {
        ...baseRecord,
        id: 3,
        category: "人工",
        amount: "500",
        record_date: "2026-05-20",
        note: "采摘工",
      },
    ];

    expect(
      filterCostRecords(records, {
        query: "西瓜",
        type: "all",
        dateRange: "month",
        month: "2026-06",
        now: "2026-06-03T16:00:00",
      }).map((r) => r.id)
    ).toEqual([2]);

    expect(
      filterCostRecords(records, {
        query: "",
        type: "cost",
        dateRange: "month",
        month: "2026-06",
        now: "2026-06-03T16:00:00",
      }).map((r) => r.id)
    ).toEqual([1]);
  });

  it("支持按茬口和人工来源筛选跳转账单", () => {
    const records: CostRecord[] = [
      {
        ...baseRecord,
        id: 1,
        cycle_id: 7,
        category: "人工",
        source_type: "labor_entry",
        source_id: 11,
      },
      {
        ...baseRecord,
        id: 2,
        cycle_id: 7,
        category: "人工",
        source_type: "operation_work_order",
        source_id: 12,
      },
      {
        ...baseRecord,
        id: 3,
        cycle_id: 8,
        category: "人工",
        source_type: "labor_entry",
        source_id: 13,
      },
    ];

    expect(
      filterCostRecords(records, {
        query: "",
        type: "cost",
        dateRange: "month",
        month: "2026-06",
        now: "2026-06-03T16:00:00",
        cycleId: 7,
        category: "人工",
        sourceType: "labor_entry",
      }).map((r) => r.id)
    ).toEqual([1]);
  });

  it("深链账单筛选支持全部日期，保证利润页跨月明细不被本月过滤", () => {
    const records: CostRecord[] = [
      {
        ...baseRecord,
        id: 1,
        cycle_id: 7,
        category: "人工",
        amount: "500",
        record_date: "2026-05-20",
        source_type: "labor_entry",
      },
      {
        ...baseRecord,
        id: 2,
        cycle_id: 7,
        category: "人工",
        amount: "600",
        record_date: "2026-06-02",
        source_type: "operation_work_order",
      },
    ];

    expect(
      filterCostRecords(records, {
        query: "",
        type: "cost",
        dateRange: "all",
        month: "2026-06",
        now: "2026-06-03T16:00:00",
        cycleId: 7,
        category: "人工",
      }).map((r) => r.id)
    ).toEqual([1, 2]);
  });
});
