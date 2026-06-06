import { TAB_CONFIG } from "../tabConfig";

describe("MainTabNavigator", () => {
  it("使用芽芽智能副驾方向的五项底部导航", () => {
    expect(Object.keys(TAB_CONFIG)).toEqual([
      "Home",
      "Cycles",
      "AgentChat",
      "Costs",
      "Settings",
    ]);
    expect(TAB_CONFIG.AgentChat.label).toBe("芽芽");
    expect(TAB_CONFIG.AgentChat.icon).toBe("sprout");
  });
});
