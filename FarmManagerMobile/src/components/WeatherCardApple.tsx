import React from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import { shadowV2 } from "../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useNavigation } from "@react-navigation/native";

interface WeatherData {
  daily?: {
    time: string[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_sum: number[];
    precipitation_hours: number[];
    windspeed_10m_max: number[];
    uv_index_max: number[];
    relative_humidity_2m_mean: number[];
    apparent_temperature_max?: number[];
    apparent_temperature_min?: number[];
  };
  hourly?: {
    time: string[];
    precipitation: number[];
    precipitation_probability?: number[];
  };
  current_weather?: {
    temperature: number;
  };
  warnings?: string[];
}

interface WeatherCardAppleProps {
  data: WeatherData | null;
  cityName?: string;
  loading?: boolean;
}

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

// UV 指数描述
const getUVLabel = (uv: number): { label: string; color: string } => {
  if (uv <= 2) return { label: "低", color: "#4CAF50" };
  if (uv <= 5) return { label: "中", color: "#FFC107" };
  if (uv <= 7) return { label: "高", color: "#FF9800" };
  if (uv <= 10) return { label: "很高", color: "#FF5722" };
  return { label: "极高", color: "#D32F2F" };
};

// 天气图标
const getWeatherIcon = (precip: number, maxTemp: number): string => {
  if (precip > 10) return "weather-pouring";
  if (precip > 5) return "weather-rainy";
  if (precip > 0) return "weather-partly-rainy";
  if (maxTemp > 30) return "weather-sunny";
  if (maxTemp < 10) return "weather-snowy";
  return "weather-partly-cloudy";
};

// 降水时段格式化
const formatPrecipHours = (hourly?: { time: string[]; precipitation: number[]; precipitation_probability?: number[] }): string[] => {
  if (!hourly?.time) return [];

  const times: string[] = [];
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];

  for (let i = 0; i < Math.min(24, hourly.time.length); i++) {
    const time = hourly.time[i];
    const precip = hourly.precipitation[i];
    const prob = hourly.precipitation_probability?.[i] || 0;

    if (time.startsWith(todayStr) && (precip > 0 || prob >= 50)) {
      const hour = parseInt(time.split('T')[1].split(':')[0]);
      times.push(`${hour}时`);
    }
  }
  return times;
};

export const WeatherCardApple: React.FC<WeatherCardAppleProps> = ({
  data,
  cityName = "本地",
  loading = false
}) => {
  const navigation = useNavigation();

  if (loading || !data?.daily?.time) {
    return (
      <View style={[styles.card, styles.loadingCard]}>
        <Text style={styles.loadingText}>加载中...</Text>
      </View>
    );
  }

  const { daily, hourly, current_weather, warnings } = data;
  const currentTemp = current_weather?.temperature ?? daily.temperature_2m_max[0];

  // 今日数据
  const todayMax = Math.round(daily.temperature_2m_max[0]);
  const todayMin = Math.round(daily.temperature_2m_min[0]);
  const todayPrecip = daily.precipitation_sum[0];
  const todayPrecipHours = daily.precipitation_hours[0];
  const todayWind = daily.windspeed_10m_max[0];
  const todayHumidity = daily.relative_humidity_2m_mean[0];
  const todayUV = daily.uv_index_max[0];
  const uvInfo = getUVLabel(todayUV);

  // 体感温度
  const feelsLikeMax = daily.apparent_temperature_max?.[0];
  const feelsLikeMin = daily.apparent_temperature_min?.[0];
  const feelsLike = feelsLikeMax !== undefined && feelsLikeMin !== undefined
    ? `${Math.round(feelsLikeMin)}~${Math.round(feelsLikeMax)}°`
    : `${todayMin}~${todayMax}°`;

  // 降水时段
  const precipTimes = formatPrecipHours(hourly);

  // 3天预报
  const forecast = daily.time.slice(0, 3).map((t, i) => {
    const d = new Date(t);
    const isToday = i === 0;
    return {
      date: isToday ? "今天" : `${d.getMonth() + 1}/${d.getDate()}`,
      weekday: WEEKDAYS[d.getDay()],
      max: Math.round(daily.temperature_2m_max[i]),
      min: Math.round(daily.temperature_2m_min[i]),
      precip: daily.precipitation_sum[i],
      icon: getWeatherIcon(daily.precipitation_sum[i], daily.temperature_2m_max[i]),
    };
  });

  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={() => navigation.navigate("WeatherDetail" as never)}
    >
      <View style={[styles.card, shadowV2.card]}>
        {/* Header */}
        <View style={styles.header}>
          <Icon name="map-marker" size={14} color={colors.textSecondary} />
          <Text style={styles.cityName}>{cityName}</Text>
        </View>

        {/* Current Temp - Big */}
        <View style={styles.currentSection}>
          <Text style={styles.currentTemp}>{Math.round(currentTemp)}°</Text>
          <View style={styles.tempRange}>
            <Text style={styles.tempRangeText}>最高 {todayMax}° · 最低 {todayMin}°</Text>
          </View>
          <View style={styles.feelsLikeRow}>
            <Icon name="thermometer" size={12} color={colors.textSecondary} />
            <Text style={styles.feelsLikeText}>体感 {feelsLike}</Text>
          </View>
        </View>

        {/* Weather Icon */}
        <View style={styles.iconSection}>
          <Icon
            name={getWeatherIcon(todayPrecip, todayMax)}
            size={80}
            color={colors.primary}
          />
        </View>

        {/* Warning Banner */}
        {warnings && warnings.length > 0 && (
          <View style={styles.warningBanner}>
            <Icon name="alert" size={16} color={colors.warning} />
            <Text style={styles.warningText}>{warnings[0]}</Text>
          </View>
        )}

        {/* Stats Grid */}
        <View style={styles.statsGrid}>
          <View style={styles.statItem}>
            <Icon name="water" size={16} color={colors.info} />
            <Text style={styles.statValue}>{todayHumidity}%</Text>
            <Text style={styles.statLabel}>湿度</Text>
          </View>
          <View style={styles.statItem}>
            <Icon name="weather-windy" size={16} color={colors.textSecondary} />
            <Text style={styles.statValue}>{Math.round(todayWind)}m/s</Text>
            <Text style={styles.statLabel}>风速</Text>
          </View>
          <View style={styles.statItem}>
            <Icon name="white-balance-sunny" size={16} color={uvInfo.color} />
            <Text style={[styles.statValue, { color: uvInfo.color }]}>{uvInfo.label}</Text>
            <Text style={styles.statLabel}>紫外线</Text>
          </View>
          <View style={styles.statItem}>
            <Icon name="umbrella" size={16} color={todayPrecip > 0 ? colors.primary : colors.textTertiary} />
            <Text style={styles.statValue}>{todayPrecip > 0 ? `${todayPrecip}mm` : "无"}</Text>
            <Text style={styles.statLabel}>降水</Text>
          </View>
        </View>

        {/* Precipitation Hours */}
        {precipTimes.length > 0 && (
          <View style={styles.precipSection}>
            <View style={styles.precipHeader}>
              <Icon name="clock-outline" size={14} color={colors.textSecondary} />
              <Text style={styles.precipTitle}>降水时段</Text>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.precipScroll}>
              {precipTimes.slice(0, 8).map((time, i) => (
                <View key={i} style={styles.precipChip}>
                  <Text style={styles.precipChipText}>{time}</Text>
                </View>
              ))}
              {precipTimes.length > 8 && (
                <View style={styles.precipChip}>
                  <Text style={styles.precipChipText}>+{precipTimes.length - 8}</Text>
                </View>
              )}
            </ScrollView>
          </View>
        )}

        {/* Forecast Row */}
        <View style={styles.forecastSection}>
          <Text style={styles.forecastTitle}>未来预报</Text>
          <View style={styles.forecastRow}>
            {forecast.map((day) => (
              <View key={day.date} style={styles.forecastDay}>
                <Text style={styles.forecastDate}>{day.date}</Text>
                <Icon name={day.icon} size={24} color={colors.text} style={styles.forecastIcon} />
                <Text style={styles.forecastTemp}>{day.min}~{day.max}°</Text>
              </View>
            ))}
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    margin: spacingV2.lg,
  },
  loadingCard: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacingV2.xxxl,
  },
  loadingText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacingV2.xs,
    marginBottom: spacingV2.sm,
  },
  cityName: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  currentSection: {
    marginBottom: spacingV2.lg,
  },
  currentTemp: {
    fontSize: 96,
    fontWeight: '200',
    color: colors.text,
    letterSpacing: -4,
    lineHeight: 100,
  },
  tempRange: {
    marginTop: spacingV2.xs,
  },
  tempRangeText: {
    fontSize: fontSizeV2.lg,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  feelsLikeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacingV2.xs,
    marginTop: spacingV2.xs,
  },
  feelsLikeText: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  iconSection: {
    position: 'absolute',
    right: spacingV2.xl,
    top: spacingV2.xxxl,
  },
  warningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacingV2.xs,
    backgroundColor: colors.warningLight,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.md,
    marginBottom: spacingV2.lg,
  },
  warningText: {
    fontSize: fontSizeV2.sm,
    color: colors.warning,
    fontWeight: '600',
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: spacingV2.xl,
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statValue: {
    fontSize: fontSizeV2.md,
    fontWeight: '700',
    color: colors.text,
    marginTop: spacingV2.xs,
  },
  statLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  precipSection: {
    marginBottom: spacingV2.xl,
  },
  precipHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacingV2.xs,
    marginBottom: spacingV2.sm,
  },
  precipTitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  precipScroll: {
    flexDirection: 'row',
  },
  precipChip: {
    backgroundColor: colors.infoLight,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: spacingV2.xs,
    borderRadius: borderRadiusV2.sm,
    marginRight: spacingV2.xs,
  },
  precipChipText: {
    fontSize: fontSizeV2.xs,
    color: colors.info,
    fontWeight: '600',
  },
  forecastSection: {
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    paddingTop: spacingV2.lg,
  },
  forecastTitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: '600',
    marginBottom: spacingV2.md,
  },
  forecastRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  forecastDay: {
    alignItems: 'center',
    flex: 1,
  },
  forecastDate: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginBottom: spacingV2.xs,
  },
  forecastIcon: {
    marginBottom: spacingV2.xs,
  },
  forecastTemp: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: '600',
  },
});
