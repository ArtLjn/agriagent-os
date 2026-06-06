import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { useSettingsStore } from "../../stores/settingsStore";
import { useCycleStore } from "../../stores/cycleStore";
import { useAuthStore } from "../../stores/authStore";
import { useCostStore } from "../../stores/costStore";
import { CITIES } from "../../data/cities";
import { CityPicker } from "../../components/CityPicker";
import { BreathingFloat } from "../../components/animations/BreathingFloat";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const getGreeting = (displayName: string) => {
  const hour = new Date().getHours();
  if (hour < 11) {
    return `早上好，${displayName}`;
  }
  if (hour < 14) {
    return `中午好，${displayName}`;
  }
  if (hour < 18) {
    return `下午好，${displayName}`;
  }
  return `晚上好，${displayName}`;
};

const QUICK_ACTIONS = [
  {
    label: "问天气",
    caption: "今天能不能打药",
    icon: "weather-partly-cloudy",
    iconBg: "#EAF5FF",
    iconColor: "#3D7BD9",
    route: "AgentChat",
  },
  {
    label: "记账",
    caption: "说一句自动整理",
    icon: "cash-plus",
    iconBg: "#FFF3E4",
    iconColor: "#B7791F",
    route: "AgentChat",
  },
  {
    label: "农事",
    caption: "看茬口和作业",
    icon: "sprout",
    iconBg: "#EDFDF3",
    iconColor: "#3B8B5C",
    route: "CycleList",
  },
  {
    label: "周报",
    caption: "让芽芽生成总结",
    icon: "file-document-outline",
    iconBg: "#F0F4F8",
    iconColor: "#64748B",
    route: "AgentChat",
  },
];

const ASSISTANT_ACTIONS = [
  {
    title: "补录昨天的农药支出",
    meta: "关联到当前茬口后，利润会更准",
    icon: "cash-sync",
    route: "CostCreate",
  },
  {
    title: "查看今日农事建议",
    meta: "天气、湿度和作物阶段已整理",
    icon: "clipboard-text-search-outline",
    route: "AdviceDetail",
  },
  {
    title: "安排下一次田间巡查",
    meta: "建议优先检查湿度和病虫害",
    icon: "calendar-check-outline",
    route: "CycleList",
  },
];

const getWeatherCondition = (
  weather: any
): "sunny" | "rainy" | "foggy" | "cold" => {
  if (!weather?.daily) {
    return "sunny";
  }
  const precip = weather.daily.precipitation_sum?.[0] || 0;
  const maxTemp = weather.daily.temperature_2m_max?.[0] || 20;
  if (precip > 5) {
    return "rainy";
  }
  if (precip > 0) {
    return "foggy";
  }
  if (maxTemp < 10) {
    return "cold";
  }
  return "sunny";
};

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation();
  const {
    weather,
    dailyAdvice,
    fetchWeather,
    fetchDailyAdvice,
    loadCachedWeather,
    cityName,
    setCity,
  } = useAgentStore();
  const {
    defaultCity,
    displayName,
    setCity: setSettingsCity,
    syncToServer,
    loadFromServer,
  } = useSettingsStore();
  const { isLoggedIn, user } = useAuthStore();
  const { cycles, fetchCycles } = useCycleStore();
  const { records, fetchRecords } = useCostStore();
  const [pickerVisible, setPickerVisible] = useState(false);

  useEffect(() => {
    // 老用户补全：已登录但服务端无城市设置时触发定位
    if (isLoggedIn) {
      (async () => {
        const serverCity = await loadFromServer();
        if (!serverCity) {
          // 服务端无设置，尝试 GPS 定位
          const { detectLocation } = require("../../utils/locationUtils");
          const { findNearestCity } = require("../../utils/cityMatcher");
          detectLocation().then((coords: any) => {
            if (coords) {
              const city = findNearestCity(coords.latitude, coords.longitude);
              setSettingsCity({
                name: city.name,
                lat: city.lat,
                lon: city.lon,
              });
              syncToServer();
            }
          });
        }
      })();
    }
  }, [isLoggedIn, loadFromServer, setSettingsCity, syncToServer]);

  useEffect(() => {
    if (defaultCity && defaultCity !== cityName) {
      const cityData = CITIES.find((c) => c.name === defaultCity);
      if (cityData) {
        setCity(cityData.name, cityData.lat, cityData.lon);
      }
    }
    loadCachedWeather();
    fetchWeather();
    fetchDailyAdvice();
    fetchCycles();
    fetchRecords();
  }, [
    defaultCity,
    loadCachedWeather,
    fetchWeather,
    fetchDailyAdvice,
    fetchCycles,
    fetchRecords,
    cityName,
    setCity,
  ]);

  const nickname = user?.nickname || displayName;
  const greeting = getGreeting(nickname);
  const weatherCondition = getWeatherCondition(weather);
  const activeCycles = cycles.filter((cycle) => cycle.status === "active");
  const currentMonth = new Date().toISOString().slice(0, 7);
  const monthRecords = records.filter((record) =>
    record.record_date?.startsWith(currentMonth)
  );
  const monthIncome = monthRecords
    .filter((record) => record.record_type === "income")
    .reduce((sum, record) => sum + Number(record.amount || 0), 0);
  const monthCost = monthRecords
    .filter((record) => record.record_type === "cost")
    .reduce((sum, record) => sum + Number(record.amount || 0), 0);
  const monthBalance = monthIncome - monthCost;
  const advicePreview =
    dailyAdvice?.preview ||
    "我会把天气、农事和账本串起来，帮你先看今天最该处理的事。";
  const todayWeather = weather?.daily
    ? {
        min: Math.round(weather.daily.temperature_2m_min?.[0] ?? 0),
        max: Math.round(weather.daily.temperature_2m_max?.[0] ?? 0),
        rain: weather.daily.precipitation_sum?.[0] ?? 0,
      }
    : null;

  const handleCitySelect = async (city: {
    name: string;
    lat: number;
    lon: number;
  }) => {
    setSettingsCity({ name: city.name, lat: city.lat, lon: city.lon });
    await setCity(city.name, city.lat, city.lon);
    await syncToServer();
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <FadeInSlideUp style={styles.headerSection}>
          <View style={styles.headerTop}>
            <View>
              <TouchableOpacity
                style={styles.cityRow}
                onPress={() => setPickerVisible(true)}
                activeOpacity={0.7}
              >
                <Icon name="map-marker" size={14} color={colors.primary} />
                <Text style={styles.cityName}>{cityName}</Text>
                <Icon name="chevron-down" size={14} color={colors.primary} />
              </TouchableOpacity>
              <Text style={styles.greeting}>{greeting}</Text>
              <Text style={styles.dateText}>
                {new Date().toLocaleDateString("zh-CN", {
                  month: "long",
                  day: "numeric",
                  weekday: "long",
                })}
              </Text>
            </View>
            <ScalePress
              onPress={() => navigation.navigate("AgentChat" as never)}
            >
              <View style={styles.aiIconBtn}>
                <Icon
                  name="message-text-outline"
                  size={20}
                  color={colors.success}
                />
              </View>
            </ScalePress>
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={60} style={styles.section}>
          <View style={styles.assistantHero}>
            <View style={styles.heroHeader}>
              <View style={styles.heroCopy}>
                <Text style={styles.heroEyebrow}>芽芽智能副驾</Text>
                <Text style={styles.heroTitle}>我先帮你把今天理清楚</Text>
                <Text style={styles.heroSubtitle} numberOfLines={2}>
                  {advicePreview}
                </Text>
              </View>
              <BreathingFloat>
                <ScalePress
                  onPress={() => navigation.navigate("AgentChat" as never)}
                >
                  <View style={styles.budAvatar}>
                    <Icon name="sprout" size={28} color={colors.success} />
                  </View>
                </ScalePress>
              </BreathingFloat>
            </View>
            <ScalePress
              onPress={() => navigation.navigate("WeatherDetail" as never)}
            >
              <View style={styles.weatherStrip}>
                <View style={styles.weatherStripIcon}>
                  <Icon
                    name={
                      weatherCondition === "rainy"
                        ? "weather-pouring"
                        : weatherCondition === "cold"
                        ? "snowflake"
                        : weatherCondition === "foggy"
                        ? "weather-fog"
                        : "white-balance-sunny"
                    }
                    size={20}
                    color={farmTheme.colors.soil}
                  />
                </View>
                <View style={styles.weatherStripCopy}>
                  <Text style={styles.weatherStripTitle}>
                    {todayWeather
                      ? `${todayWeather.min}°~${todayWeather.max}° · ${
                          todayWeather.rain > 0 ? "可能有雨" : "适合巡田"
                        }`
                      : "天气同步中"}
                  </Text>
                  <Text style={styles.weatherStripMeta}>
                    点开查看逐小时天气和预警
                  </Text>
                </View>
                <Icon
                  name="chevron-right"
                  size={18}
                  color="rgba(255,255,255,0.58)"
                />
              </View>
            </ScalePress>
            <View style={styles.heroMetricRow}>
              <View style={styles.heroMetric}>
                <Text style={styles.heroMetricValue}>
                  {activeCycles.length}
                </Text>
                <Text style={styles.heroMetricLabel}>进行中茬口</Text>
              </View>
              <View style={styles.heroMetricDivider} />
              <View style={styles.heroMetric}>
                <Text style={styles.heroMetricValue}>
                  {dailyAdvice?.items?.length || 0}
                </Text>
                <Text style={styles.heroMetricLabel}>今日建议</Text>
              </View>
              <View style={styles.heroMetricDivider} />
              <View style={styles.heroMetric}>
                <Text style={styles.heroMetricValue}>
                  {monthRecords.length}
                </Text>
                <Text style={styles.heroMetricLabel}>本月账目</Text>
              </View>
            </View>
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={120} style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>待你确认</Text>
            <TouchableOpacity
              style={styles.sectionLink}
              onPress={() => navigation.navigate("AgentChat" as never)}
              activeOpacity={0.75}
            >
              <Text style={styles.sectionLinkText}>问芽芽</Text>
              <Icon name="chevron-right" size={16} color={colors.success} />
            </TouchableOpacity>
          </View>
          <View style={styles.actionList}>
            {ASSISTANT_ACTIONS.map((action, index) => (
              <ScalePress
                key={action.title}
                onPress={() => {
                  if (action.route === "AdviceDetail") {
                    navigation.navigate(
                      "AdviceDetail" as never,
                      {
                        items: dailyAdvice?.items,
                        preview: dailyAdvice?.preview,
                        weatherCondition,
                        createdAt: dailyAdvice?.created_at,
                      } as never
                    );
                    return;
                  }
                  navigation.navigate(action.route as never);
                }}
              >
                <View
                  style={[
                    styles.actionItem,
                    index === ASSISTANT_ACTIONS.length - 1 &&
                      styles.actionItemLast,
                  ]}
                >
                  <View style={styles.actionIcon}>
                    <Icon name={action.icon} size={18} color={colors.success} />
                  </View>
                  <View style={styles.actionCopy}>
                    <Text style={styles.actionTitle}>{action.title}</Text>
                    <Text style={styles.actionMeta}>{action.meta}</Text>
                  </View>
                  <Icon
                    name="chevron-right"
                    size={20}
                    color={colors.textTertiary}
                  />
                </View>
              </ScalePress>
            ))}
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={180} style={styles.section}>
          <View style={styles.quickActionsGrid}>
            {QUICK_ACTIONS.map((action) => (
              <ScalePress
                key={action.label}
                onPress={() => {
                  if (action.route === "AgentChat") {
                    navigation.navigate("AgentChat" as never);
                    return;
                  }
                  navigation.navigate(action.route as never);
                }}
              >
                <View style={styles.quickActionItem}>
                  <View
                    style={[
                      styles.quickActionIcon,
                      { backgroundColor: action.iconBg },
                    ]}
                  >
                    <Icon
                      name={action.icon}
                      size={22}
                      color={action.iconColor}
                    />
                  </View>
                  <View style={styles.quickActionCopy}>
                    <Text style={styles.quickActionLabel}>{action.label}</Text>
                    <Text style={styles.quickActionCaption} numberOfLines={1}>
                      {action.caption}
                    </Text>
                  </View>
                </View>
              </ScalePress>
            ))}
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={240} style={styles.section}>
          <View style={styles.insightRow}>
            <View style={styles.financeCard}>
              <Text style={styles.cardEyebrow}>本月经营</Text>
              <Text
                style={[
                  styles.balanceText,
                  monthBalance >= 0
                    ? styles.balancePositive
                    : styles.balanceNegative,
                ]}
              >
                {monthBalance >= 0 ? "+" : "-"}¥
                {Math.abs(monthBalance).toFixed(0)}
              </Text>
              <Text style={styles.financeMeta}>
                收入 ¥{monthIncome.toFixed(0)} · 支出 ¥{monthCost.toFixed(0)}
              </Text>
            </View>
            <View style={styles.focusCard}>
              <View style={styles.focusIcon}>
                <Icon name="target-variant" size={24} color={colors.success} />
              </View>
              <Text style={styles.cardEyebrow}>今日重点</Text>
              <Text style={styles.focusTitle}>先处理待确认事项</Text>
            </View>
          </View>
        </FadeInSlideUp>
      </ScrollView>

      <CityPicker
        visible={pickerVisible}
        selectedCity={cityName}
        onSelect={handleCitySelect}
        onClose={() => setPickerVisible(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: farmTheme.colors.page,
  },
  scrollContent: {
    paddingBottom: 112,
  },
  headerSection: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.lg,
    paddingBottom: spacingV2.sm,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  cityRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginBottom: spacingV2.sm,
    alignSelf: "flex-start",
    backgroundColor: farmTheme.colors.leafSoft,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 4,
    borderRadius: borderRadiusV2.md,
  },
  cityName: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: farmTheme.colors.leaf,
  },
  greeting: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: 0,
  },
  dateText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  aiIconBtn: {
    width: 44,
    height: 44,
    borderRadius: borderRadiusV2.full,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 4,
  },
  section: {
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
  },
  assistantHero: {
    borderRadius: farmTheme.radius.panel,
    padding: spacingV2.lg,
    backgroundColor: "#254130",
    ...farmTheme.shadow.float,
    overflow: "hidden",
  },
  heroHeader: {
    flexDirection: "row",
    gap: spacingV2.md,
    alignItems: "flex-start",
  },
  heroCopy: {
    flex: 1,
  },
  heroEyebrow: {
    fontSize: fontSizeV2.xs,
    color: "rgba(228, 242, 214, 0.72)",
    fontWeight: "700",
    marginBottom: spacingV2.sm,
  },
  heroTitle: {
    fontSize: 25,
    lineHeight: 31,
    fontWeight: "900",
    color: "#FFFFFF",
    letterSpacing: 0,
    marginBottom: spacingV2.sm,
  },
  heroSubtitle: {
    fontSize: fontSizeV2.sm,
    lineHeight: 20,
    color: "rgba(255, 255, 255, 0.74)",
  },
  budAvatar: {
    width: 58,
    height: 58,
    borderRadius: 22,
    backgroundColor: "#F2F8E9",
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#CDE7B0",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.22,
    shadowRadius: 18,
    elevation: 5,
  },
  heroMetricRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacingV2.lg,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(255, 255, 255, 0.12)",
  },
  weatherStrip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    marginTop: spacingV2.md,
    padding: spacingV2.sm,
    borderRadius: 22,
    backgroundColor: "rgba(255, 255, 255, 0.10)",
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.10)",
  },
  weatherStripIcon: {
    width: 40,
    height: 40,
    borderRadius: 16,
    backgroundColor: "#FFF6DC",
    alignItems: "center",
    justifyContent: "center",
  },
  weatherStripCopy: {
    flex: 1,
    minWidth: 0,
  },
  weatherStripTitle: {
    fontSize: fontSizeV2.sm,
    color: "#FFFFFF",
    fontWeight: "800",
    marginBottom: 2,
  },
  weatherStripMeta: {
    fontSize: fontSizeV2.xs,
    color: "rgba(255, 255, 255, 0.62)",
    fontWeight: "600",
  },
  heroMetric: {
    flex: 1,
  },
  heroMetricValue: {
    fontSize: fontSizeV2.xl,
    fontWeight: "900",
    color: "#D8F0BC",
  },
  heroMetricLabel: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: "rgba(255, 255, 255, 0.62)",
    fontWeight: "600",
  },
  heroMetricDivider: {
    width: 1,
    height: 32,
    backgroundColor: "rgba(255, 255, 255, 0.12)",
    marginHorizontal: spacingV2.md,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.sm,
  },
  sectionTitle: {
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "900",
  },
  sectionLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  sectionLinkText: {
    fontSize: fontSizeV2.sm,
    color: colors.success,
    fontWeight: "700",
  },
  actionList: {
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    paddingHorizontal: spacingV2.lg,
    ...farmTheme.shadow.card,
  },
  actionItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    paddingVertical: spacingV2.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  actionItemLast: {
    borderBottomWidth: 0,
  },
  actionIcon: {
    width: 42,
    height: 42,
    borderRadius: 16,
    backgroundColor: colors.successMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  actionCopy: {
    flex: 1,
  },
  actionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 3,
  },
  actionMeta: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  quickActionsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.md,
  },
  quickActionItem: {
    width: 165,
    minHeight: 84,
    borderRadius: 24,
    backgroundColor: farmTheme.colors.surface,
    padding: spacingV2.md,
    alignItems: "center",
    justifyContent: "flex-start",
    flexDirection: "row",
    gap: spacingV2.md,
    ...farmTheme.shadow.card,
  },
  quickActionIcon: {
    width: 44,
    height: 44,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 0,
  },
  quickActionCopy: {
    flex: 1,
    minWidth: 0,
  },
  quickActionLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "800",
    textAlign: "left",
    marginBottom: 3,
  },
  quickActionCaption: {
    fontSize: 10,
    color: colors.textTertiary,
    textAlign: "left",
    lineHeight: 14,
  },
  insightRow: {
    flexDirection: "row",
    gap: spacingV2.md,
  },
  financeCard: {
    flex: 1.2,
    borderRadius: 26,
    padding: spacingV2.lg,
    backgroundColor: farmTheme.colors.surface,
    ...farmTheme.shadow.card,
  },
  focusCard: {
    flex: 1,
    borderRadius: 26,
    padding: spacingV2.lg,
    backgroundColor: farmTheme.colors.surfaceSoft,
    ...farmTheme.shadow.card,
  },
  focusIcon: {
    width: 40,
    height: 40,
    borderRadius: 16,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.md,
  },
  cardEyebrow: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "700",
    marginBottom: spacingV2.xs,
  },
  balanceText: {
    fontSize: 24,
    fontWeight: "900",
    letterSpacing: 0,
  },
  balancePositive: {
    color: colors.income,
  },
  balanceNegative: {
    color: colors.expense,
  },
  financeMeta: {
    marginTop: spacingV2.sm,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    lineHeight: 16,
  },
  focusTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.text,
  },
});
