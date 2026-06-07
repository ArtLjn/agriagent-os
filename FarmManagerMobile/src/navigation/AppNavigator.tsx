import React, { useEffect } from "react";
import { View, ActivityIndicator, StyleSheet } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { MainTabNavigator } from "./MainTabNavigator";
import { CycleListScreen } from "../screens/cycle/CycleListScreen";
import { CycleDetailScreen } from "../screens/cycle/CycleDetailScreen";
import { CycleCreateScreen } from "../screens/cycle/CycleCreateScreen";
import { PlantingUnitManageScreen } from "../screens/cycle/PlantingUnitManageScreen";
import { WorkOrderCreateScreen } from "../screens/cycle/WorkOrderCreateScreen";
import { LogListScreen } from "../screens/log/LogListScreen";
import { LogCreateScreen } from "../screens/log/LogCreateScreen";
import { CostCreateScreen } from "../screens/cost/CostCreateScreen";
import { CostListScreen } from "../screens/cost/CostListScreen";
import { CostCategoryScreen } from "../screens/cost/CostCategoryScreen";
import { ProfitScreen } from "../screens/cost/ProfitScreen";
import { WorkerListScreen } from "../screens/worker/WorkerListScreen";
import { WageCreateScreen } from "../screens/worker/WageCreateScreen";
import { WorkerCreateScreen } from "../screens/worker/WorkerCreateScreen";
import { AgentChatScreen } from "../screens/agent/AgentChatScreen";
import { AgentReportScreen } from "../screens/agent/AgentReportScreen";
import { GuideScreen } from "../screens/settings/GuideScreen";
import { SettingsScreen } from "../screens/settings/SettingsScreen";
import { AboutScreen } from "../screens/settings/AboutScreen";
import { DebtListScreen } from "../screens/debt/DebtListScreen";
import { DebtCreateScreen } from "../screens/debt/DebtCreateScreen";
import { CropTemplateScreen } from "../screens/crop/CropTemplateScreen";
import { CropTemplateCreateScreen } from "../screens/crop/CropTemplateCreateScreen";
import { WeatherDetailScreen } from "../screens/weather/WeatherDetailScreen";
import { WeatherAlertScreen } from "../screens/weather/WeatherAlertScreen";
import { AdviceDetailScreen } from "../screens/advice/AdviceDetailScreen";
import { FarmDashboardScreen } from "../screens/dashboard/FarmDashboardScreen";
import { LoginScreen } from "../screens/auth/LoginScreen";
import { RegisterScreen } from "../screens/auth/RegisterScreen";
import { WelcomeScreen } from "../screens/auth/WelcomeScreen";
import { useAuthStore, setOnUnauthorized } from "../stores/authStore";
import { colors } from "../theme/colors";

export type RootStackParamList = {
  Main: undefined;
  CycleList: undefined;
  CycleDetail: { cycleId: number };
  CycleCreate: undefined;
  PlantingUnits: { cycleId: number };
  WorkOrderCreate: {
    cycleId: number;
    cropName?: string;
    operationType?: string;
  };
  WorkerList: undefined;
  WorkerCreate:
    | {
        workerName?: string;
      }
    | undefined;
  WageCreate: {
    cycleId?: number;
    cropName?: string;
    operationType?: string;
    workerId?: number;
    workerName?: string;
    unitPrice?: string;
  };
  LogList: { cycleId: number };
  LogCreate: { cycleId: number };
  CostList:
    | {
        filters?: {
          cycleId?: number;
          category?: string;
          sourceType?: string;
          sourceId?: number;
          title?: string;
        };
      }
    | undefined;
  CostCreate: undefined;
  CostCategory: undefined;
  Profit: { cycleId: number };
  AgentChat: { cycleId?: number };
  AgentReport: {
    cycleId?: number;
    content?: string;
    reportType?: string;
    createdAt?: string;
    reportId?: number;
  };
  Guide: undefined;
  DebtList: undefined;
  DebtCreate: undefined;
  CropTemplate: undefined;
  CropTemplateCreate: undefined;
  WeatherDetail: undefined;
  WeatherAlert: { warnings: string[]; cityName: string };
  AdviceDetail: {
    items?: import("../api/types").AdviceItem[];
    preview?: string;
    weatherCondition?: "sunny" | "rainy" | "foggy" | "cold";
    createdAt?: string;
  };
  FarmDashboard: undefined;
  Settings: undefined;
  About: undefined;
  Welcome: undefined;
  Login: undefined;
  Register: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const screenOptions = {
  headerStyle: {
    backgroundColor: colors.surface,
  },
  headerTintColor: colors.text,
  headerTitleStyle: {
    fontSize: 18,
    fontWeight: "700" as const,
    color: colors.text,
  },
  headerShadowVisible: false,
  contentStyle: {
    backgroundColor: colors.background,
  },
};

export const AppNavigator: React.FC = () => {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn);
  const isInitializing = useAuthStore((s) => s.isInitializing);
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (isInitializing) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer
      key={isLoggedIn ? "main" : "auth"}
      ref={(ref) => {
        if (ref) {
          setOnUnauthorized(() => {
            try {
              ref.reset({ index: 0, routes: [{ name: "Welcome" }] });
            } catch {}
          });
        }
      }}
    >
      <Stack.Navigator screenOptions={screenOptions}>
        {isLoggedIn ? (
          <>
            <Stack.Screen
              name="Main"
              component={MainTabNavigator}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="CycleList"
              component={CycleListScreen}
              options={{ title: "种植规划" }}
            />
            <Stack.Screen
              name="CycleDetail"
              component={CycleDetailScreen}
              options={{ title: "茬口详情" }}
            />
            <Stack.Screen
              name="CycleCreate"
              component={CycleCreateScreen}
              options={{ title: "新建茬口" }}
            />
            <Stack.Screen
              name="PlantingUnits"
              component={PlantingUnitManageScreen}
              options={{ title: "种植单元" }}
            />
            <Stack.Screen
              name="WorkOrderCreate"
              component={WorkOrderCreateScreen}
              options={{ title: "记录作业" }}
            />
            <Stack.Screen
              name="WorkerList"
              component={WorkerListScreen}
              options={{ title: "工人管理" }}
            />
            <Stack.Screen
              name="WorkerCreate"
              component={WorkerCreateScreen}
              options={{ title: "新增工人" }}
            />
            <Stack.Screen
              name="WageCreate"
              component={WageCreateScreen}
              options={{ title: "记工资" }}
            />
            <Stack.Screen
              name="LogList"
              component={LogListScreen}
              options={{ title: "农事记录" }}
            />
            <Stack.Screen
              name="LogCreate"
              component={LogCreateScreen}
              options={{ title: "快速打卡" }}
            />
            <Stack.Screen
              name="CostCreate"
              component={CostCreateScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="CostList"
              component={CostListScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="CostCategory"
              component={CostCategoryScreen}
              options={{ title: "分类管理" }}
            />
            <Stack.Screen
              name="Profit"
              component={ProfitScreen}
              options={{ title: "利润统计" }}
            />
            <Stack.Screen
              name="AgentChat"
              component={AgentChatScreen}
              options={{ title: "芽芽顾问" }}
            />
            <Stack.Screen
              name="AgentReport"
              component={AgentReportScreen}
              options={{ title: "种植报告" }}
            />
            <Stack.Screen
              name="Guide"
              component={GuideScreen}
              options={{ title: "使用指南" }}
            />
            <Stack.Screen
              name="Settings"
              component={SettingsScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="About"
              component={AboutScreen}
              options={{ title: "关于" }}
            />
            <Stack.Screen
              name="DebtList"
              component={DebtListScreen}
              options={{ title: "赊账管理" }}
            />
            <Stack.Screen
              name="DebtCreate"
              component={DebtCreateScreen}
              options={{ title: "记赊账" }}
            />
            <Stack.Screen
              name="CropTemplate"
              component={CropTemplateScreen}
              options={{ title: "作物模板" }}
            />
            <Stack.Screen
              name="CropTemplateCreate"
              component={CropTemplateCreateScreen}
              options={{ title: "创建作物模板" }}
            />
            <Stack.Screen
              name="WeatherDetail"
              component={WeatherDetailScreen}
              options={{ title: "天气详情", headerShown: false }}
            />
            <Stack.Screen
              name="WeatherAlert"
              component={WeatherAlertScreen}
              options={{ title: "天气预警", headerShown: false }}
            />
            <Stack.Screen
              name="AdviceDetail"
              component={AdviceDetailScreen}
              options={{ title: "农事建议", headerShown: false }}
            />
            <Stack.Screen
              name="FarmDashboard"
              component={FarmDashboardScreen}
              options={{ headerShown: false }}
            />
          </>
        ) : (
          <>
            <Stack.Screen
              name="Welcome"
              component={(props: any) => (
                <WelcomeScreen
                  onNavigateToLogin={() => props.navigation.navigate("Login")}
                  onNavigateToRegister={() =>
                    props.navigation.navigate("Register")
                  }
                />
              )}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="Login"
              component={(props: any) => (
                <LoginScreen
                  onNavigateToRegister={() =>
                    props.navigation.navigate("Register")
                  }
                />
              )}
              options={{ headerShown: false, animation: "slide_from_bottom" }}
            />
            <Stack.Screen
              name="Register"
              component={(props: any) => (
                <RegisterScreen
                  onNavigateToLogin={() => props.navigation.navigate("Login")}
                />
              )}
              options={{ headerShown: false, animation: "slide_from_bottom" }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background,
  },
});
