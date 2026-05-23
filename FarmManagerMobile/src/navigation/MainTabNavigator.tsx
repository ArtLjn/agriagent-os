import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {Text, StyleSheet} from 'react-native';
import {colors} from '../theme/colors';
import {fontSize} from '../theme/spacing';
import {HomeScreen} from '../screens/home/HomeScreen';
import {CycleListScreen} from '../screens/cycle/CycleListScreen';
import {CostListScreen} from '../screens/cost/CostListScreen';
import {SettingsScreen} from '../screens/settings/SettingsScreen';

export type MainTabParamList = {
  Home: undefined;
  Cycles: undefined;
  Costs: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const TabLabel: React.FC<{label: string; focused: boolean}> = ({
  label,
  focused,
}) => (
  <Text style={[styles.tabLabel, focused && styles.tabLabelActive]}>
    {label}
  </Text>
);

export const MainTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={{
      headerShown: false,
      tabBarStyle: styles.tabBar,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.textSecondary,
    }}>
    <Tab.Screen
      name="Home"
      component={HomeScreen}
      options={{
        tabBarLabel: ({focused}) => (
          <TabLabel label="首页" focused={focused} />
        ),
      }}
    />
    <Tab.Screen
      name="Cycles"
      component={CycleListScreen}
      options={{
        tabBarLabel: ({focused}) => (
          <TabLabel label="茬口" focused={focused} />
        ),
      }}
    />
    <Tab.Screen
      name="Costs"
      component={CostListScreen}
      options={{
        tabBarLabel: ({focused}) => (
          <TabLabel label="记账" focused={focused} />
        ),
      }}
    />
    <Tab.Screen
      name="Settings"
      component={SettingsScreen}
      options={{
        tabBarLabel: ({focused}) => (
          <TabLabel label="我的" focused={focused} />
        ),
      }}
    />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 64,
    paddingBottom: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  tabLabel: {
    fontSize: fontSize.sm,
  },
  tabLabelActive: {
    fontWeight: '600',
    color: colors.primary,
  },
});
