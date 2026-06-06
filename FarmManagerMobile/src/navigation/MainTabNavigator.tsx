import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2 } from "../theme/spacing";
import { HomeScreen } from "../screens/home/HomeScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { CycleListScreen } from "../screens/cycle/CycleListScreen";
import { CostListScreen } from "../screens/cost/CostListScreen";
import { ProfileScreen } from "../screens/profile/ProfileScreen";
import { TAB_CONFIG, type MainTabParamList } from "./tabConfig";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const Tab = createBottomTabNavigator<MainTabParamList>();

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
              size={route.name === "AgentChat" ? 24 : 21}
              color={focused ? colors.success : colors.tabInactive}
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
    <Tab.Screen name="Cycles" component={CycleListScreen} />
    <Tab.Screen name="AgentChat" component={AgentChatScreen} />
    <Tab.Screen name="Costs" component={CostListScreen} />
    <Tab.Screen name="Settings" component={ProfileScreen} />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 76,
    backgroundColor: "rgba(255, 255, 255, 0.96)",
    borderTopWidth: 0,
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    shadowColor: colors.success,
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
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    minWidth: 54,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: spacingV2.xs,
    borderRadius: 20,
    backgroundColor: colors.successMuted,
    gap: 2,
  },
  tabLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.tabInactive,
    fontWeight: "500",
  },
  tabLabelActive: {
    fontSize: fontSizeV2.xs,
    color: colors.success,
    fontWeight: "700",
  },
});
