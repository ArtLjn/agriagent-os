import { useCostStore } from "../costStore";

jest.mock("../../api/client", () => ({
  costApi: {
    getRecords: jest.fn(),
    createRecord: jest.fn(),
    deleteRecord: jest.fn(),
    getProfit: jest.fn(),
  },
}));

const { costApi } = require("../../api/client");

beforeEach(() => {
  jest.clearAllMocks();
  useCostStore.setState({
    records: [],
    profit: null,
    loading: false,
    error: null,
  });
});

describe("costStore", () => {
  it("fetchRecords 将完整账单筛选参数下推到 API", async () => {
    costApi.getRecords.mockResolvedValueOnce({ data: { items: [] } });

    await useCostStore.getState().fetchRecords({
      cycle_id: 7,
      category: "人工",
      source_type: "labor_entry",
      source_id: 11,
    });

    expect(costApi.getRecords).toHaveBeenCalledWith({
      cycle_id: 7,
      category: "人工",
      source_type: "labor_entry",
      source_id: 11,
    });
  });
});
