import React from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {MainTabNavigator} from './MainTabNavigator';
import {CycleDetailScreen} from '../screens/cycle/CycleDetailScreen';
import {CycleCreateScreen} from '../screens/cycle/CycleCreateScreen';
import {LogListScreen} from '../screens/log/LogListScreen';
import {LogCreateScreen} from '../screens/log/LogCreateScreen';
import {CostCreateScreen} from '../screens/cost/CostCreateScreen';
import {CostCategoryScreen} from '../screens/cost/CostCategoryScreen';
import {ProfitScreen} from '../screens/cost/ProfitScreen';
import {AgentChatScreen} from '../screens/agent/AgentChatScreen';
import {AgentReportScreen} from '../screens/agent/AgentReportScreen';
import {GuideScreen} from '../screens/settings/GuideScreen';
import {DebtListScreen} from '../screens/debt/DebtListScreen';
import {DebtCreateScreen} from '../screens/debt/DebtCreateScreen';
import {CropTemplateScreen} from '../screens/crop/CropTemplateScreen';
import {colors} from '../theme/colors';

export type RootStackParamList = {
  Main: undefined;
  CycleDetail: {cycleId: number};
  CycleCreate: undefined;
  LogList: {cycleId: number};
  LogCreate: {cycleId: number};
  CostCreate: undefined;
  CostCategory: undefined;
  Profit: {cycleId: number};
  AgentChat: {cycleId?: number};
  AgentReport: {cycleId?: number; content?: string; reportType?: string; createdAt?: string; reportId?: number};
  Guide: undefined;
  DebtList: undefined;
  DebtCreate: undefined;
  CropTemplate: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export const AppNavigator: React.FC = () => (
  <NavigationContainer>
    <Stack.Navigator
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.headerBg,
        },
        headerTintColor: colors.headerText,
        headerTitleStyle: {
          fontSize: 18,
          fontWeight: '700',
        },
        headerShadowVisible: false,
        contentStyle: {
          backgroundColor: colors.background,
        },
      }}>
      <Stack.Screen
        name="Main"
        component={MainTabNavigator}
        options={{headerShown: false}}
      />
      <Stack.Screen
        name="CycleDetail"
        component={CycleDetailScreen}
        options={{title: '茬口详情'}}
      />
      <Stack.Screen
        name="CycleCreate"
        component={CycleCreateScreen}
        options={{title: '新建茬口'}}
      />
      <Stack.Screen
        name="LogList"
        component={LogListScreen}
        options={{title: '农事记录'}}
      />
      <Stack.Screen
        name="LogCreate"
        component={LogCreateScreen}
        options={{title: '快速打卡'}}
      />
      <Stack.Screen
        name="CostCreate"
        component={CostCreateScreen}
        options={{title: '记一笔'}}
      />
      <Stack.Screen
        name="CostCategory"
        component={CostCategoryScreen}
        options={{title: '分类管理'}}
      />
      <Stack.Screen
        name="Profit"
        component={ProfitScreen}
        options={{title: '利润统计'}}
      />
      <Stack.Screen
        name="AgentChat"
        component={AgentChatScreen}
        options={{title: '农事顾问'}}
      />
      <Stack.Screen
        name="AgentReport"
        component={AgentReportScreen}
        options={{title: '种植报告'}}
      />
      <Stack.Screen
        name="Guide"
        component={GuideScreen}
        options={{title: '使用指南'}}
      />
      <Stack.Screen
        name="DebtList"
        component={DebtListScreen}
        options={{title: '赊账管理'}}
      />
      <Stack.Screen
        name="DebtCreate"
        component={DebtCreateScreen}
        options={{title: '记赊账'}}
      />
      <Stack.Screen
        name="CropTemplate"
        component={CropTemplateScreen}
        options={{title: '作物模板'}}
      />
    </Stack.Navigator>
  </NavigationContainer>
);
