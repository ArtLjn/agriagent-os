import { normalizeCostRecords } from "../costRecordNormalize";
import type { CostRecord } from "../../../../api/types";

const baseRecord: CostRecord = {
  id: 1,
  cycle_id: null,
  record_type: "cost",
  category: "化肥",
  amount: "120",
  record_date: new Date().toISOString().split("T")[0],
  note: "化肥120块",
};

describe("costRecordNormalize", () => {
  it("为今天缺少创建时间的记录补充本地创建时间", () => {
    const records = normalizeCostRecords(
      [baseRecord],
      "2026-06-04T09:30:00.000Z"
    );

    expect(records[0].created_at).toBe("2026-06-04T09:30:00.000Z");
  });

  it("保留后端返回的真实创建时间", () => {
    const records = normalizeCostRecords(
      [{ ...baseRecord, created_at: "2026-06-04T08:10:00" }],
      "2026-06-04T09:30:00.000Z"
    );

    expect(records[0].created_at).toBe("2026-06-04T08:10:00");
  });
});
