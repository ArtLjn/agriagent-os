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
import { CITIES } from "../../data/cities";
import { WeatherCardV2 } from "../../components/WeatherCardV2";
import { AdviceCard } from "../../components/AdviceCard";
import { AIPet } from "../../components/AIPet";
import { CityPicker } from "../../components/CityPicker";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 11) {
    return "早上好，农友";
  }
  if (hour < 14) {
    return "中午好，农友";
  }
  if (hour < 18) {
    return "下午好，农友";
  }
  return "晚上好，农友";
};

const QUICK_ACTIONS = [
  {
    label: "种植规划",
    icon: "seed-plus",
    bgColor: colors.qaPlanting,
    iconColor: "#16A34A",
    route: "CycleCreate",
  },
  {
    label: "农事提醒",
    icon: "bell-ring",
    bgColor: colors.qaReminder,
    iconColor: "#5B8CFF",
    route: "AgentChat",
  },
  {
    label: "天气趋势",
    icon: "weather-partly-cloudy",
    bgColor: colors.qaWeather,
    iconColor: "#E8923C",
    route: "AgentChat",
  },
  {
    label: "病虫害识别",
    icon: "bug",
    bgColor: colors.qaPest,
    iconColor: "#EF4444",
    route: "AgentChat",
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
    refreshDailyAdvice,
    loading: agentLoading,
    cityName,
    setCity,
  } = useAgentStore();
  const { defaultCity, setDefaultCity } = useSettingsStore();
  const { fetchCycles } = useCycleStore();
  const [pickerVisible, setPickerVisible] = useState(false);

  useEffect(() => {
    if (defaultCity !== cityName) {
      const cityData = CITIES.find((c) => c.name === defaultCity);
      if (cityData) {
        setCity(cityData.name, cityData.lat, cityData.lon);
      }
    }
    fetchWeather();
    fetchDailyAdvice();
    fetchCycles();
  }, [fetchWeather, fetchDailyAdvice, fetchCycles]);

  const greeting = getGreeting();
  const weatherCondition = getWeatherCondition(weather);

  const handleCitySelect = (city: {
    name: string;
    lat: number;
    lon: number;
  }) => {
    setCity(city.name, city.lat, city.lon);
    setDefaultCity(city.name);
    fetchWeather();
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
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
                <Icon name="robot" size={22} color={colors.primary} />
              </View>
            </ScalePress>
          </View>
        </FadeInSlideUp>

        {/* Weather Card */}
        <FadeInSlideUp delay={80} style={styles.section}>
          <WeatherCardV2 data={weather} />
        </FadeInSlideUp>

        {/* AI Briefing Card */}
        <FadeInSlideUp delay={160} style={styles.section}>
          <AdviceCard
            advice={dailyAdvice?.advice || null}
            items={dailyAdvice?.items}
            loading={agentLoading}
            onPress={() => navigation.navigate("AgentChat" as never)}
            onRefresh={() => refreshDailyAdvice()}
            weatherCondition={weatherCondition}
          />
        </FadeInSlideUp>

        {/* Quick Actions */}
        <FadeInSlideUp delay={240} style={styles.section}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.quickActionsContainer}
          >
            {QUICK_ACTIONS.map((action) => (
              <ScalePress
                key={action.label}
                onPress={() => navigation.navigate(action.route as never)}
              >
                <View
                  style={[
                    styles.quickActionCard,
                    { backgroundColor: action.bgColor },
                  ]}
                >
                  <View style={styles.quickActionIcon}>
                    <Icon
                      name={action.icon}
                      size={24}
                      color={action.iconColor}
                    />
                  </View>
                  <Text style={styles.quickActionLabel}>{action.label}</Text>
                </View>
              </ScalePress>
            ))}
          </ScrollView>
        </FadeInSlideUp>
      </ScrollView>

      <AIPet />

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
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: 120,
  },
  headerSection: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.lg,
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
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 4,
    borderRadius: borderRadiusV2.md,
  },
  cityName: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  greeting: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.5,
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
    backgroundColor: colors.aiPetBg,
    alignItems: "center",
    justifyContent: "center",
  },
  section: {
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.xl,
  },
  quickActionsContainer: {
    paddingRight: spacingV2.lg,
    gap: spacingV2.md,
  },
  quickActionCard: {
    width: 110,
    height: 120,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.md,
    justifyContent: "space-between",
  },
  quickActionIcon: {
    width: 44,
    height: 44,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: "rgba(255,255,255,0.7)",
    alignItems: "center",
    justifyContent: "center",
  },
  quickActionLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "600",
  },
});
