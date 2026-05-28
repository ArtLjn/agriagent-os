import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2 } from "../theme/spacing";
import { shadowV2 } from "../theme/designTokens";
import { HomeScreen } from "../screens/home/HomeScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { CostListScreen } from "../screens/cost/CostListScreen";
import { ProfileScreen } from "../screens/profile/ProfileScreen";
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
  AgentChat: { label: "助手", icon: "sprout", activeIcon: "sprout" },
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
    <Tab.Screen name="Settings" component={ProfileScreen} />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 72,
    backgroundColor: colors.surface,
    borderTopWidth: 0,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 8,
    paddingHorizontal: spacingV2.sm,
    paddingBottom: 8,
  },
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    paddingVertical: spacingV2.xs,
    gap: 2,
  },
  tabItemActive: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    paddingVertical: spacingV2.xs,
    gap: 2,
  },
  tabLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.tabInactive,
    fontWeight: "500",
  },
  tabLabelActive: {
    fontSize: fontSizeV2.xs,
    color: colors.primary,
    fontWeight: "600",
  },
});
