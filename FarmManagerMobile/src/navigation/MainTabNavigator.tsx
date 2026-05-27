import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { View, Text, StyleSheet, Platform } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import { shadowV2 } from "../theme/designTokens";
import LinearGradient from "react-native-linear-gradient";
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
          <View style={styles.tabItem}>
            {focused ? (
              <LinearGradient
                colors={["#5B8CFF", "#7A7DFF"]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.capsule}
              >
                <Icon name={config.activeIcon} size={20} color="#FFFFFF" />
                <Text style={styles.capsuleLabel}>{config.label}</Text>
              </LinearGradient>
            ) : (
              <View style={styles.inactiveItem}>
                <Icon name={config.icon} size={22} color={colors.tabInactive} />
                <Text style={styles.inactiveLabel}>{config.label}</Text>
              </View>
            )}
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
    position: "absolute",
    bottom: 16,
    left: 16,
    right: 16,
    height: 72,
    borderRadius: borderRadiusV2.tab,
    backgroundColor: Platform.select({
      ios: "rgba(255,255,255,0.85)",
      android: "rgba(255,255,255,0.95)",
    }),
    borderTopWidth: 0,
    ...shadowV2.card,
    elevation: 10,
  },
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
  },
  capsule: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    gap: 4,
  },
  capsuleLabel: {
    fontSize: fontSizeV2.sm,
    color: "#FFFFFF",
    fontWeight: "600",
  },
  inactiveItem: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacingV2.sm,
  },
  inactiveLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.tabInactive,
    marginTop: 2,
    fontWeight: "500",
  },
});
