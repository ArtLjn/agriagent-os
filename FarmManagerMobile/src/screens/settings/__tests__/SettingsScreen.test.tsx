import React from "react";
import { fireEvent, render } from "@testing-library/react-native";

import { SettingsScreen } from "../SettingsScreen";

const mockSetDisplayName = jest.fn();

const mockSettingsState = {
  defaultFarmName: "睢宁农场",
  defaultCity: "苏州",
  crops: ["西瓜"],
  reminderTime: "08:00",
  notificationEnabled: true,
  weatherAlertEnabled: true,
  displayName: "农友",
  setCity: jest.fn(),
  setCrops: jest.fn(),
  setNotificationEnabled: jest.fn(),
  setWeatherAlertEnabled: jest.fn(),
  setDisplayName: mockSetDisplayName,
  syncToServer: jest.fn(),
};

jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({
    goBack: jest.fn(),
    navigate: jest.fn(),
  }),
}));

jest.mock("../../../components/CityPicker", () => ({
  CityPicker: () => null,
}));

jest.mock("../../../stores/authStore", () => ({
  useAuthStore: (selector: any) => selector({ logout: jest.fn() }),
}));

jest.mock("../../../stores/agentStore", () => ({
  useAgentStore: {
    getState: () => ({ setCity: jest.fn() }),
  },
}));

jest.mock("../../../stores/settingsStore", () => ({
  useSettingsStore: Object.assign(
    (selector?: any) =>
      typeof selector === "function"
        ? selector(mockSettingsState)
        : mockSettingsState,
    {
      getState: () => ({ setReminderTime: jest.fn() }),
    }
  ),
}));

jest.mock("@react-native-async-storage/async-storage", () => ({
  clear: jest.fn(),
}));

describe("SettingsScreen", () => {
  beforeEach(() => {
    mockSetDisplayName.mockClear();
  });

  it("uses an in-app input dialog for display name on Android", () => {
    const { getByText, getByPlaceholderText } = render(<SettingsScreen />);

    fireEvent.press(getByText("AI 称呼我"));

    const input = getByPlaceholderText("例如：老李、农友、管理员");
    fireEvent.changeText(input, "老李");
    fireEvent.press(getByText("保存"));

    expect(mockSetDisplayName).toHaveBeenCalledWith("老李");
  });
});
