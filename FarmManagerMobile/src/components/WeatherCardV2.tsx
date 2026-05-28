import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import LinearGradient from "react-native-linear-gradient";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import { appGradients } from "../theme/gradients";
import { shadowV2 } from "../theme/designTokens";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { useNavigation } from "@react-navigation/native";

interface WeatherDay {
  date: string;
  weekday: string;
  maxTemp: number;
  minTemp: number;
  precipitation: number;
}

interface WeatherCardV2Props {
  data: {
    daily: {
      time: string[];
      temperature_2m_max: number[];
      temperature_2m_min: number[];
      precipitation_sum: number[];
    };
  } | null;
}

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

export const WeatherCardV2: React.FC<WeatherCardV2Props> = ({ data }) => {
  const navigation = useNavigation();

  if (!data?.daily) {
    return (
      <LinearGradient
        {...appGradients.weatherCard}
        style={[styles.card, shadowV2.card]}
      >
        <Text style={styles.emptyText}>暂无天气数据</Text>
      </LinearGradient>
    );
  }

  const { time, temperature_2m_max, temperature_2m_min, precipitation_sum } =
    data.daily;

  const days: WeatherDay[] = time.slice(0, 3).map((t, i) => {
    const d = new Date(t);
    const isToday = i === 0;
    return {
      date: isToday ? "今天" : `${d.getMonth() + 1}/${d.getDate()}`,
      weekday: WEEKDAYS[d.getDay()],
      maxTemp: Math.round(temperature_2m_max[i]),
      minTemp: Math.round(temperature_2m_min[i]),
      precipitation: precipitation_sum[i],
    };
  });

  const today = days[0];
  const todayIcon = getWeatherIcon(today.precipitation, today.maxTemp);
  const todayLabel = getWeatherLabel(today.precipitation, today.maxTemp);

  return (
    <TouchableOpacity
      activeOpacity={0.9}
      onPress={() => navigation.navigate("WeatherDetail" as never)}
    >
      <LinearGradient
        {...appGradients.weatherCard}
        style={[styles.card, shadowV2.card]}
      >
        <View style={styles.topSection}>
          <View style={styles.topLeft}>
            <View style={styles.locationRow}>
              <Icon name="map-marker" size={14} color="rgba(255,255,255,0.8)" />
              <Text style={styles.locationText}>本地天气</Text>
            </View>
            <Text style={styles.bigTemp}>
              {today.minTemp}° ~ {today.maxTemp}°
            </Text>
            <Text style={styles.weatherLabel}>{todayLabel}</Text>
            <Text style={styles.feelsLike}>体感 {today.maxTemp - 2}°</Text>
          </View>
          <View style={styles.topRight}>
            <Icon name={todayIcon} size={64} color="#FFFFFF" />
          </View>
        </View>

        <View style={styles.divider} />

        <View style={styles.forecastRow}>
          {days.map((d) => {
            const iconName = getWeatherIcon(d.precipitation, d.maxTemp);
            return (
              <View key={d.date} style={styles.dayItem}>
                <Text style={styles.dayDate}>{d.date}</Text>
                <Text style={styles.dayWeekday}>{d.weekday}</Text>
                <Icon
                  name={iconName}
                  size={24}
                  color="#FFFFFF"
                  style={styles.dayIcon}
                />
                <Text style={styles.dayTemp}>{d.maxTemp}°</Text>
              </View>
            );
          })}
        </View>
      </LinearGradient>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    overflow: "hidden",
  },
  emptyText: {
    fontSize: fontSizeV2.md,
    color: colors.textInverse,
    textAlign: "center",
    paddingVertical: spacingV2.xxl,
  },
  topSection: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  topLeft: {
    flex: 1,
  },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginBottom: spacingV2.sm,
  },
  locationText: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255,255,255,0.8)",
  },
  bigTemp: {
    fontSize: fontSizeV2.xxxxl,
    fontWeight: "800",
    color: "#FFFFFF",
    letterSpacing: -1,
  },
  weatherLabel: {
    fontSize: fontSizeV2.md,
    color: "rgba(255,255,255,0.8)",
    marginTop: 2,
  },
  feelsLike: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255,255,255,0.6)",
    marginTop: 4,
  },
  topRight: {
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacingV2.md,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(255,255,255,0.2)",
    marginVertical: spacingV2.lg,
  },
  forecastRow: {
    flexDirection: "row",
    justifyContent: "space-around",
  },
  dayItem: {
    alignItems: "center",
    flex: 1,
  },
  dayDate: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255,255,255,0.9)",
    fontWeight: "600",
  },
  dayWeekday: {
    fontSize: fontSizeV2.xs,
    color: "rgba(255,255,255,0.6)",
    marginTop: 2,
  },
  dayIcon: {
    marginVertical: spacingV2.sm,
  },
  dayTemp: {
    fontSize: fontSizeV2.md,
    color: "#FFFFFF",
    fontWeight: "700",
  },
});
