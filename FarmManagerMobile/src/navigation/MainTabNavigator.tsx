import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { farmTheme } from "../theme/farmTheme";
import { spacingV2, fontSizeV2 } from "../theme/spacing";
import { HomeScreen } from "../screens/home/HomeScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { CycleListScreen } from "../screens/cycle/CycleListScreen";
import { CostListScreen } from "../screens/cost/CostListScreen";
import { ProfileScreen } from "../screens/profile/ProfileScreen";
import { TAB_CONFIG, type MainTabParamList } from "./tabConfig";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

export type { MainTabParamList } from "./tabConfig";

const Tab = createBottomTabNavigator<MainTabParamList>();

export const MainTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={({ route }) => ({
      headerShown: false,
      tabBarStyle: styles.tabBar,
      tabBarShowLabel: false,
      tabBarIcon: ({ focused }) => {
        const config = TAB_CONFIG[route.name];
        const isAssistant = route.name === "AgentChat";
        return (
          <View
            style={[
              styles.tabItem,
              focused && styles.tabItemActive,
              isAssistant && styles.assistantTab,
              isAssistant && focused && styles.assistantTabActive,
            ]}
          >
            <View style={isAssistant ? styles.assistantIconWrap : undefined}>
              <Icon
                name={focused ? config.activeIcon : config.icon}
                size={isAssistant ? 25 : 21}
                color={
                  isAssistant
                    ? "#FFFFFF"
                    : focused
                    ? farmTheme.colors.leaf
                    : colors.tabInactive
                }
              />
            </View>
            {!isAssistant && (
              <Text
                style={focused ? styles.tabLabelActive : styles.tabLabel}
                numberOfLines={1}
              >
                {config.label}
              </Text>
            )}
          </View>
        );
      },
    })}
  >
    <Tab.Screen name="Home" component={HomeScreen} />
    <Tab.Screen name="Cycles" component={CycleListScreen} />
    <Tab.Screen name="AgentChat" component={AgentChatScreen} />
    <Tab.Screen name="Costs" component={CostListScreen} />
    <Tab.Screen name="Settings" component={ProfileScreen} />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 80,
    backgroundColor: "rgba(255, 255, 255, 0.97)",
    borderTopWidth: 0,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: -6 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
    elevation: 8,
    paddingHorizontal: spacingV2.xs,
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
    minWidth: 52,
    paddingHorizontal: spacingV2.sm,
    borderRadius: 20,
    backgroundColor: farmTheme.colors.leafSoft,
  },
  assistantTab: {
    marginTop: -18,
  },
  assistantTabActive: {
    backgroundColor: "transparent",
  },
  assistantIconWrap: {
    width: 56,
    height: 56,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leaf,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.22,
    shadowRadius: 18,
    elevation: 8,
  },
  tabLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.tabInactive,
    fontWeight: "500",
  },
  tabLabelActive: {
    fontSize: fontSizeV2.xs,
    color: farmTheme.colors.leaf,
    fontWeight: "700",
  },
});
