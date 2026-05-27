import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2 } from "../theme/spacing";
import { shadowV2 } from "../theme/designTokens";
import { HomeScreen } from "../screens/home/HomeScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { CostListScreen } from "../screens/cost/CostListScreen";
import { SettingsScreen } from "../screens/settings/SettingsScreen";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export type MainTabParamList = {
  Home: undefined;
  AgentChat: undefined;
  Costs: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const TAB_CONFIG: Record<
  keyof MainTabParamList,
  { label: string; icon: string; activeIcon: string }
> = {
  Home: { label: "首页", icon: "home-outline", activeIcon: "home" },
  AgentChat: { label: "AI助手", icon: "robot-outline", activeIcon: "robot" },
  Costs: { label: "记账", icon: "cash-multiple", activeIcon: "cash-multiple" },
  Settings: { label: "我的", icon: "account-outline", activeIcon: "account" },
};

export const MainTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={({ route }) => ({
      headerShown: false,
      tabBarStyle: styles.tabBar,
      tabBarShowLabel: false,
      tabBarIcon: ({ focused }) => {
        const config = TAB_CONFIG[route.name];
        return (
          <View style={focused ? styles.tabItemActive : styles.tabItem}>
            <Icon
              name={focused ? config.activeIcon : config.icon}
              size={22}
              color={focused ? colors.primary : colors.tabInactive}
            />
            <Text
              style={focused ? styles.tabLabelActive : styles.tabLabel}
              numberOfLines={1}
            >
              {config.label}
            </Text>
          </View>
        );
      },
    })}
  >
    <Tab.Screen name="Home" component={HomeScreen} />
    <Tab.Screen name="AgentChat" component={AgentChatScreen} />
    <Tab.Screen name="Costs" component={CostListScreen} />
    <Tab.Screen name="Settings" component={SettingsScreen} />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 64,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    ...shadowV2.light,
    elevation: 4,
  },
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    paddingVertical: spacingV2.sm,
  },
  tabItemActive: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    paddingVertical: spacingV2.sm,
  },
  tabLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.tabInactive,
    marginTop: 2,
    fontWeight: "500",
  },
  tabLabelActive: {
    fontSize: fontSizeV2.xs,
    color: colors.primary,
    marginTop: 2,
    fontWeight: "600",
  },
});
