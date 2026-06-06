import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import { CostAmountPanel } from "../CostAmountPanel";

describe("CostAmountPanel", () => {
  it("switches record type and applies quick amount", () => {
    const onAmountChange = jest.fn();
    const onTypeChange = jest.fn();

    const { getByText } = render(
      <CostAmountPanel
        amount=""
        recordType="cost"
        onAmountChange={onAmountChange}
        onTypeChange={onTypeChange}
      />
    );

    fireEvent.press(getByText("收入"));
    fireEvent.press(getByText("¥100"));

    expect(onTypeChange).toHaveBeenCalledWith("income");
    expect(onAmountChange).toHaveBeenCalledWith("100");
  });
});
