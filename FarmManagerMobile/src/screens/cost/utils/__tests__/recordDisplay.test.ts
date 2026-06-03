import {
  filterCostRecords,
  formatRecordAmount,
  formatRecordTimestamp,
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
});
