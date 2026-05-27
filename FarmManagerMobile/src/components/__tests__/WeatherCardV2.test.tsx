import React from "react";
import { render } from "@testing-library/react-native";
import { WeatherCardV2 } from "../WeatherCardV2";

jest.mock("react-native-linear-gradient", () => "LinearGradient");
jest.mock("@react-navigation/native", () => ({
  useNavigation: () => ({ navigate: jest.fn() }),
}));

const mockWeatherData = {
  daily: {
    time: ["2026-05-27", "2026-05-28", "2026-05-29"],
    temperature_2m_max: [28, 30, 25],
    temperature_2m_min: [18, 20, 16],
    precipitation_sum: [0, 2, 8],
  },
};

describe("WeatherCardV2", () => {
  it("renders weather data correctly", () => {
    const { getByText, getAllByText } = render(
      <WeatherCardV2 data={mockWeatherData} />
    );
    expect(getByText("18° ~ 28°")).toBeTruthy();
    expect(getByText("多云")).toBeTruthy();
    expect(getAllByText("今天").length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty state when no data", () => {
    const { getByText } = render(<WeatherCardV2 data={null} />);
    expect(getByText("暂无天气数据")).toBeTruthy();
  });

  it("shows 3-day forecast", () => {
    const { getByText, getAllByText } = render(
      <WeatherCardV2 data={mockWeatherData} />
    );
    expect(getAllByText("今天").length).toBeGreaterThanOrEqual(1);
    expect(getByText("5/28")).toBeTruthy();
    expect(getByText("5/29")).toBeTruthy();
  });
});
