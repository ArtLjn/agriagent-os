import React from 'react';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {View, StyleSheet, Text} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, fontSize} from '../theme/spacing';
import {HomeScreen} from '../screens/home/HomeScreen';
import {AgentChatScreen} from '../screens/agent/AgentChatScreen';
import {CostListScreen} from '../screens/cost/CostListScreen';
import {SettingsScreen} from '../screens/settings/SettingsScreen';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

export type MainTabParamList = {
  Home: undefined;
  AgentChat: undefined;
  Costs: undefined;
  Settings: undefined;
};

const Tab = createBottomTabNavigator<MainTabParamList>();

const TAB_CONFIG: Record<keyof MainTabParamList, {label: string; icon: string; activeIcon: string}> = {
  Home: {label: '首页', icon: 'home-outline', activeIcon: 'home'},
  AgentChat: {label: 'AI助手', icon: 'robot-outline', activeIcon: 'robot'},
  Costs: {label: '记账', icon: 'cash-multiple', activeIcon: 'cash-multiple'},
  Settings: {label: '我的', icon: 'account-outline', activeIcon: 'account'},
};

export const MainTabNavigator: React.FC = () => (
  <Tab.Navigator
    screenOptions={({route}) => ({
      headerShown: false,
      tabBarStyle: styles.tabBar,
      tabBarActiveTintColor: colors.primary,
      tabBarInactiveTintColor: colors.tabInactive,
      tabBarShowLabel: true,
      tabBarLabel: ({focused, color}) => (
        <Text style={[styles.tabLabel, focused && styles.tabLabelActive, {color}]}>
          {TAB_CONFIG[route.name].label}
        </Text>
      ),
      tabBarIcon: ({focused, color}) => (
        <View style={[styles.iconContainer, focused && styles.iconContainerActive]}>
          <Icon
            name={focused ? TAB_CONFIG[route.name].activeIcon : TAB_CONFIG[route.name].icon}
            size={22}
            color={color}
          />
        </View>
      ),
    })}>
    <Tab.Screen name="Home" component={HomeScreen} />
    <Tab.Screen name="AgentChat" component={AgentChatScreen} />
    <Tab.Screen name="Costs" component={CostListScreen} />
    <Tab.Screen name="Settings" component={SettingsScreen} />
  </Tab.Navigator>
);

const styles = StyleSheet.create({
  tabBar: {
    height: 72,
    paddingBottom: 10,
    paddingTop: 6,
    backgroundColor: colors.tabBg,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    shadowColor: colors.shadow,
    shadowOffset: {width: 0, height: -2},
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 8,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 2,
  },
  iconContainerActive: {
    backgroundColor: colors.primaryMuted,
  },
  tabLabel: {
    fontSize: fontSize.xs,
    fontWeight: '500',
    marginTop: 2,
  },
  tabLabelActive: {
    fontWeight: '700',
  },
});
