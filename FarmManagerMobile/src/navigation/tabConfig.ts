export type MainTabParamList = {
  Home: undefined;
  Cycles: undefined;
  AgentChat: undefined;
  Costs: undefined;
  Settings: undefined;
};

export const TAB_CONFIG: Record<
  keyof MainTabParamList,
  { label: string; icon: string; activeIcon: string }
> = {
  Home: { label: "首页", icon: "home-outline", activeIcon: "home" },
  Cycles: {
    label: "农事",
    icon: "calendar-check-outline",
    activeIcon: "calendar-check",
  },
  AgentChat: { label: "芽芽", icon: "sprout", activeIcon: "sprout" },
  Costs: { label: "记账", icon: "cash-multiple", activeIcon: "cash-multiple" },
  Settings: { label: "我的", icon: "account-outline", activeIcon: "account" },
};
