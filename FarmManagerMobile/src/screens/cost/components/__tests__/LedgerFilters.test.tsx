import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import { LedgerFilters } from "../LedgerFilters";

describe("LedgerFilters", () => {
  it("changes type and date filters from compact controls", () => {
    const onTypeChange = jest.fn();
    const onDateRangeChange = jest.fn();

    const { getByText } = render(
      <LedgerFilters
        filter="all"
        dateRange="month"
        categoryList={[]}
        categoryFilter={null}
        onFilterChange={onTypeChange}
        onDateRangeChange={onDateRangeChange}
        onCategoryFilterChange={jest.fn()}
      />
    );

    fireEvent.press(getByText("支出"));
    fireEvent.press(getByText("近7天"));

    expect(onTypeChange).toHaveBeenCalledWith("cost");
    expect(onDateRangeChange).toHaveBeenCalledWith("week");
  });
});
