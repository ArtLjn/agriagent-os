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
import { CITIES } from "../../data/cities";
import { WeatherCardV2 } from "../../components/WeatherCardV2";
import { CompactAdviceCard } from "../../components/CompactAdviceCard";
import { CityPicker } from "../../components/CityPicker";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
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
    label: "种植规划",
    icon: "sprout",
    iconBg: "#EDFDF3",
    iconColor: "#3B8B5C",
    route: "CycleList",
  },
  {
    label: "作物模板",
    icon: "seed",
    iconBg: "#FFF8E8",
    iconColor: "#B48A3E",
    route: "CropTemplate",
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
    loadCachedWeather,
    loading: agentLoading,
    cityName,
    setCity,
  } = useAgentStore();
  const { defaultCity, displayName, setCity: setSettingsCity, syncToServer, loadFromServer } = useSettingsStore();
  const { isLoggedIn, user } = useAuthStore();
  const { fetchCycles } = useCycleStore();
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
              setSettingsCity({ name: city.name, lat: city.lat, lon: city.lon });
              syncToServer();
            }
          });
        }
      })();
    }
  }, [isLoggedIn]);

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
  }, [defaultCity, loadCachedWeather, fetchWeather, fetchDailyAdvice, fetchCycles]);

  const nickname = user?.nickname || displayName;
  const greeting = getGreeting(nickname);
  const weatherCondition = getWeatherCondition(weather);

  const handleCitySelect = (city: {
    name: string;
    lat: number;
    lon: number;
  }) => {
    setCity(city.name, city.lat, city.lon);
    setSettingsCity({ name: city.name, lat: city.lat, lon: city.lon });
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
                <Icon name="message-text-outline" size={20} color={colors.primary} />
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
          <CompactAdviceCard
            preview={dailyAdvice?.preview || ""}
            itemCount={dailyAdvice?.items?.length || 0}
            loading={agentLoading}
            weatherCondition={weatherCondition}
            onPress={() =>
              navigation.navigate("AdviceDetail" as never, {
                items: dailyAdvice?.items,
                preview: dailyAdvice?.preview,
                weatherCondition,
                createdAt: dailyAdvice?.created_at,
              } as never)
            }
            onRefresh={() => refreshDailyAdvice()}
          />
        </FadeInSlideUp>

        {/* Quick Actions */}
        <FadeInSlideUp delay={240} style={styles.section}>
          <View style={styles.quickActionsCard}>
            <View style={styles.quickActionsGrid}>
              {QUICK_ACTIONS.map((action) => (
                <ScalePress
                  key={action.label}
                  onPress={() => navigation.navigate(action.route as never)}
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
                    <Text style={styles.quickActionLabel} numberOfLines={1}>
                      {action.label}
                    </Text>
                  </View>
                </ScalePress>
              ))}
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
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacingV2.xxxl,
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
  quickActionsCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.xl,
    paddingHorizontal: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  quickActionsGrid: {
    flexDirection: "row",
    justifyContent: "space-around",
    alignItems: "flex-start",
  },
  quickActionItem: {
    alignItems: "center",
    width: 72,
  },
  quickActionIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  quickActionLabel: {
    fontSize: 13,
    color: colors.text,
    fontWeight: "500",
    textAlign: "center",
    lineHeight: 18,
  },
});
