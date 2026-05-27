import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import { appGradients } from "../../theme/gradients";
import { shadowV2 } from "../../theme/designTokens";
import { FadeInSlideUp } from "../../components/animations/FadeInSlideUp";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

const getWeatherIcon = (precipitation: number, maxTemp: number) => {
  if (precipitation > 5) {
    return "weather-pouring";
  }
  if (precipitation > 0) {
    return "weather-rainy";
  }
  if (maxTemp > 30) {
    return "weather-sunny";
  }
  if (maxTemp < 10) {
    return "weather-snowy";
  }
  return "weather-partly-cloudy";
};

const getWeatherLabel = (precipitation: number, maxTemp: number) => {
  if (precipitation > 10) {
    return "大雨";
  }
  if (precipitation > 5) {
    return "中雨";
  }
  if (precipitation > 0) {
    return "小雨";
  }
  if (maxTemp > 32) {
    return "炎热";
  }
  if (maxTemp > 28) {
    return "晴热";
  }
  if (maxTemp < 5) {
    return "寒冷";
  }
  if (maxTemp < 12) {
    return "凉爽";
  }
  return "多云";
};

// Generate simulated hourly data from daily temperature range
const generateHourlyData = (minTemp: number, maxTemp: number) => {
  const hours = [];
  for (let i = 0; i < 24; i += 3) {
    // Simple sine curve approximation for daily temperature
    const hourFactor = Math.sin(((i - 6) / 24) * Math.PI * 2) * 0.5 + 0.5;
    const temp = Math.round(minTemp + (maxTemp - minTemp) * hourFactor);
    hours.push({ hour: i, temp });
  }
  return hours;
};

export const WeatherDetailScreen: React.FC = () => {
  const navigation = useNavigation();
  const { weather, cityName } = useAgentStore();

  if (!weather?.daily) {
    return (
      <SafeAreaView style={styles.container}>
        <LinearGradient
          {...appGradients.weatherDetail}
          style={StyleSheet.absoluteFill}
        />
        <View style={styles.center}>
          <Text style={styles.emptyText}>暂无天气数据</Text>
        </View>
      </SafeAreaView>
    );
  }

  const { time, temperature_2m_max, temperature_2m_min, precipitation_sum } =
    weather.daily;

  const today = {
    maxTemp: Math.round(temperature_2m_max[0]),
    minTemp: Math.round(temperature_2m_min[0]),
    precipitation: precipitation_sum[0],
  };

  const todayLabel = getWeatherLabel(today.precipitation, today.maxTemp);
  const todayIcon = getWeatherIcon(today.precipitation, today.maxTemp);
  const hourlyData = generateHourlyData(today.minTemp, today.maxTemp);

  const weekDays = time.slice(0, 7).map((t, i) => {
    const d = new Date(t);
    return {
      date: i === 0 ? "今天" : `${d.getMonth() + 1}/${d.getDate()}`,
      weekday: WEEKDAYS[d.getDay()],
      maxTemp: Math.round(temperature_2m_max[i]),
      minTemp: Math.round(temperature_2m_min[i]),
      precipitation: precipitation_sum[i],
    };
  });

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <LinearGradient
        {...appGradients.weatherDetail}
        style={StyleSheet.absoluteFill}
      />

      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          style={styles.backBtn}
        >
          <Icon name="chevron-left" size={28} color={colors.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>{cityName}</Text>
        <View style={styles.backBtn} />
      </View>

      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {/* Big Temperature */}
        <FadeInSlideUp>
          <View style={styles.bigTempSection}>
            <Icon name={todayIcon} size={80} color={colors.primary} />
            <Text style={styles.bigTemp}>{today.maxTemp}°</Text>
            <Text style={styles.weatherCondition}>{todayLabel}</Text>
            <Text style={styles.tempRange}>
              最高 {today.maxTemp}° · 最低 {today.minTemp}°
            </Text>
          </View>
        </FadeInSlideUp>

        {/* Hourly Forecast */}
        <FadeInSlideUp delay={80}>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>24小时预报</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.hourlyRow}>
                {hourlyData.map((h) => (
                  <View key={h.hour} style={[styles.hourCard, shadowV2.light]}>
                    <Text style={styles.hourText}>{h.hour}:00</Text>
                    <Text style={styles.hourTemp}>{h.temp}°</Text>
                  </View>
                ))}
              </View>
            </ScrollView>
          </View>
        </FadeInSlideUp>

        {/* 7-Day Forecast */}
        <FadeInSlideUp delay={160}>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>7日预报</Text>
            <View style={[styles.weekCard, shadowV2.light]}>
              {weekDays.map((d, i) => {
                const icon = getWeatherIcon(d.precipitation, d.maxTemp);
                return (
                  <View
                    key={i}
                    style={[
                      styles.weekRow,
                      i < weekDays.length - 1 && styles.weekRowBorder,
                    ]}
                  >
                    <Text style={styles.weekDate}>{d.date}</Text>
                    <Text style={styles.weekWeekday}>{d.weekday}</Text>
                    <Icon name={icon} size={20} color={colors.primary} />
                    <View style={styles.weekTempBar}>
                      <View style={styles.weekTempTrack}>
                        <View
                          style={[
                            styles.weekTempFill,
                            {
                              left: `${((d.minTemp + 10) / 50) * 100}%`,
                              right: `${100 - ((d.maxTemp + 10) / 50) * 100}%`,
                            },
                          ]}
                        />
                      </View>
                    </View>
                    <Text style={styles.weekMinTemp}>{d.minTemp}°</Text>
                    <Text style={styles.weekMaxTemp}>{d.maxTemp}°</Text>
                  </View>
                );
              })}
            </View>
          </View>
        </FadeInSlideUp>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
  },
  scrollContent: {
    paddingBottom: spacingV2.xxxl,
  },
  bigTempSection: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
  },
  bigTemp: {
    fontSize: 80,
    fontWeight: "200",
    color: colors.text,
    marginTop: spacingV2.md,
  },
  weatherCondition: {
    fontSize: fontSizeV2.xl,
    color: colors.textSecondary,
    marginTop: spacingV2.xs,
  },
  tempRange: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: spacingV2.sm,
  },
  section: {
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.xl,
  },
  sectionTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  hourlyRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
    paddingRight: spacingV2.lg,
  },
  hourCard: {
    backgroundColor: "rgba(255,255,255,0.6)",
    borderRadius: borderRadiusV2.lg,
    padding: spacingV2.md,
    alignItems: "center",
    minWidth: 64,
    backdropFilter: "blur(20px)",
  },
  hourText: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
  },
  hourTemp: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginTop: spacingV2.xs,
  },
  weekCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    overflow: "hidden",
  },
  weekRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacingV2.sm,
    gap: spacingV2.sm,
  },
  weekRowBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  weekDate: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "600",
    width: 50,
  },
  weekWeekday: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    width: 36,
  },
  weekTempBar: {
    flex: 1,
    height: 4,
    justifyContent: "center",
  },
  weekTempTrack: {
    height: 4,
    backgroundColor: colors.borderLight,
    borderRadius: 2,
  },
  weekTempFill: {
    position: "absolute",
    height: 4,
    backgroundColor: colors.primaryLight,
    borderRadius: 2,
  },
  weekMinTemp: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    width: 32,
    textAlign: "right",
  },
  weekMaxTemp: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "700",
    width: 32,
    textAlign: "right",
  },
});
