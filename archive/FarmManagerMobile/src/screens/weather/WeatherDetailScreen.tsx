import React from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
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
import Svg, {
  Path,
  Defs,
  LinearGradient as SvgLinearGradient,
  Stop,
  Circle,
  G,
  Text as SvgText,
} from "react-native-svg";

const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const SCREEN_WIDTH = Dimensions.get("window").width;

type WeekDayForecast = {
  date: string;
  weekday: string;
  maxTemp: number;
  minTemp: number;
  precipitation: number;
};

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

const generateHourlyData = (minTemp: number, maxTemp: number) => {
  const hours = [];
  for (let i = 0; i < 24; i += 2) {
    const factor = Math.sin(((i - 6) / 24) * Math.PI * 2) * 0.5 + 0.5;
    const temp = Math.round(minTemp + (maxTemp - minTemp) * factor);
    hours.push({ hour: i, temp });
  }
  return hours;
};

interface HourlyChartProps {
  data: { hour: number; temp: number }[];
}

const HourlyTemperatureChart: React.FC<HourlyChartProps> = ({ data }) => {
  const pointSpacing = 52;
  const hPadding = 24;
  const width = data.length * pointSpacing + hPadding * 2;
  const height = 180;
  const padding = { top: 32, bottom: 24 };
  const chartHeight = height - padding.top - padding.bottom;

  const temps = data.map((d) => d.temp);
  const minT = Math.min(...temps) - 2;
  const maxT = Math.max(...temps) + 2;
  const range = maxT - minT || 1;

  const points = data.map((d, i) => {
    const x = hPadding + i * pointSpacing + pointSpacing / 2;
    const y = padding.top + chartHeight - ((d.temp - minT) / range) * chartHeight;
    return {
      x: isNaN(x) ? 0 : x,
      y: isNaN(y) ? padding.top + chartHeight / 2 : y,
      temp: d.temp ?? 20,
      hour: d.hour ?? 0,
    };
  });

  const linePath = React.useMemo(() => {
    if (points.length < 2) {
      return "";
    }
    let p = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[Math.max(0, i - 1)];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[Math.min(points.length - 1, i + 2)];
      const cp1x = p1.x + (p2.x - p0.x) * 0.15;
      const cp1y = p1.y + (p2.y - p0.y) * 0.15;
      const cp2x = p2.x - (p3.x - p1.x) * 0.15;
      const cp2y = p2.y - (p3.y - p1.y) * 0.15;
      p += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
    }
    return p;
  }, [points]);

  const fillPath = `${linePath} L ${points[points.length - 1].x} ${height} L ${
    points[0].x
  } ${height} Z`;

  return (
    <Svg width={width} height={height}>
      <Defs>
        <SvgLinearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={colors.primary} stopOpacity="0.3" />
          <Stop offset="1" stopColor={colors.primary} stopOpacity="0" />
        </SvgLinearGradient>
      </Defs>
      <Path d={fillPath} fill="url(#areaFill)" />
      <Path
        d={linePath}
        fill="none"
        stroke={colors.primary}
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {points.map((p, i) => (
        <G key={i}>
          <Circle cx={p.x} cy={p.y} r={5} fill={colors.primary} />
          <Circle cx={p.x} cy={p.y} r={2.5} fill="#fff" />
          <SvgText
            x={p.x}
            y={p.y - 12}
            textAnchor="middle"
            fontSize={12}
            fontWeight="600"
            fill={colors.text}
          >
            {p.temp}°
          </SvgText>
          <SvgText
            x={p.x}
            y={height - 4}
            textAnchor="middle"
            fontSize={11}
            fill={colors.textSecondary}
          >
            {p.hour.toString().padStart(2, '0')}:00
          </SvgText>
        </G>
      ))}
    </Svg>
  );
};

export const WeatherDetailScreen: React.FC = () => {
  const navigation = useNavigation();
  const { weather, cityName, fetchWeather } = useAgentStore();

  React.useEffect(() => {
    fetchWeather(7);
  }, [fetchWeather]);

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

  // 预警数据
  const warnings = (weather as any)?.warnings as string[] | undefined;

  // 解析第一条预警的严重级别
  const getFirstAlertInfo = (warnings: string[]) => {
    const first = warnings[0];
    const match = first.match(/^\[(RED|ORANGE|YELLOW|BLUE)\]\s*/);
    let severity = match?.[1] ?? "BLUE";
    let title = match ? first.replace(match[0], "") : first;
    if (!match) {
      if (title.includes("红色")) severity = "RED";
      else if (title.includes("橙色")) severity = "ORANGE";
      else if (title.includes("黄色")) severity = "YELLOW";
    }
    // 取标题前部分作为预览
    const preview = title.split("[")[0]?.trim() ?? title;
    return { severity, preview };
  };

  const alertConfig: Record<string, { color: string; bgColor: string; icon: string }> = {
    RED: { color: "#C0392B", bgColor: "#FDEBEB", icon: "alert-octagon" },
    ORANGE: { color: "#E67E22", bgColor: "#FEF3E2", icon: "alert" },
    YELLOW: { color: "#D4A017", bgColor: "#FEF9E7", icon: "alert-circle" },
    BLUE: { color: "#2E86C1", bgColor: "#EBF5FB", icon: "information" },
  };

  // 使用真实的 hourly 数据，如果没有则回退到模拟数据
  const hourlyData = React.useMemo(() => {
    if (weather.hourly?.time && weather.hourly?.temperature_2m && weather.hourly.time.length > 0) {
      const times: string[] = weather.hourly.time;
      const temps: number[] = weather.hourly.temperature_2m;
      const data = times.slice(0, 24).map((t: string, i: number) => ({
        hour: new Date(t).getHours(),
        temp: temps[i] !== undefined && temps[i] !== null ? Math.round(temps[i]) : 20,
      }));
      // 过滤掉无效数据
      return data.filter(d => !isNaN(d.temp) && !isNaN(d.hour));
    }
    return generateHourlyData(today.minTemp, today.maxTemp);
  }, [weather.hourly, today.minTemp, today.maxTemp]);

  const weekMin = temperature_2m_min.length > 0 ? Math.min(...temperature_2m_min.slice(0, 7)) : 0;
  const weekMax = temperature_2m_max.length > 0 ? Math.max(...temperature_2m_max.slice(0, 7)) : 30;
  const weekRange = weekMax - weekMin || 1;

  const weekDays: WeekDayForecast[] = time.slice(0, 7).map((t: string, i: number) => {
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
        <FadeInSlideUp>
          <View style={styles.bigTempSection}>
            <Icon name={todayIcon} size={72} color={colors.primary} />
            <Text style={styles.bigTemp}>{today.maxTemp}°</Text>
            <Text style={styles.weatherCondition}>{todayLabel}</Text>
            <Text style={styles.tempRange}>
              最高 {today.maxTemp}° · 最低 {today.minTemp}°
            </Text>
          </View>
        </FadeInSlideUp>

        {/* 预警横幅 */}
        {warnings && warnings.length > 0 && (
          <FadeInSlideUp delay={60}>
            {(() => {
              const { severity, preview } = getFirstAlertInfo(warnings);
              const cfg = alertConfig[severity] ?? alertConfig.BLUE;
              return (
                <View style={styles.alertSection}>
                  <TouchableOpacity
                    activeOpacity={0.85}
                    style={[
                      styles.alertBanner,
                      { backgroundColor: cfg.bgColor },
                      shadowV2.light,
                    ]}
                    onPress={() =>
                      navigation.navigate("WeatherAlert" as never, {
                        warnings,
                        cityName,
                      } as never)
                    }
                  >
                    <View
                      style={[
                        styles.alertIconWrap,
                        { backgroundColor: cfg.color },
                      ]}
                    >
                      <Icon name={cfg.icon as any} size={20} color="#FFF" />
                    </View>
                    <View style={styles.alertTextWrap}>
                      <Text
                        style={[styles.alertTitle, { color: cfg.color }]}
                        numberOfLines={1}
                      >
                        {cfg.color === "#C0392B"
                          ? "红色预警"
                          : cfg.color === "#E67E22"
                            ? "橙色预警"
                            : cfg.color === "#D4A017"
                              ? "黄色预警"
                              : "蓝色预警"}
                      </Text>
                      <Text style={styles.alertDesc} numberOfLines={1}>
                        {preview}
                      </Text>
                    </View>
                    <Icon
                      name="chevron-right"
                      size={20}
                      color={colors.textTertiary}
                    />
                  </TouchableOpacity>
                </View>
              );
            })()}
          </FadeInSlideUp>
        )}

        <FadeInSlideUp delay={80}>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>24小时预报</Text>
            <View style={[styles.chartCard, shadowV2.light]}>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                nestedScrollEnabled
                scrollEventThrottle={16}
              >
                <HourlyTemperatureChart data={hourlyData} />
              </ScrollView>
            </View>
          </View>
        </FadeInSlideUp>

        <FadeInSlideUp delay={160}>
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>7日预报</Text>
            <View style={[styles.weekCard, shadowV2.light]}>
              {weekDays.map((d: WeekDayForecast, i: number) => {
                const icon = getWeatherIcon(d.precipitation, d.maxTemp);
                const leftPct = ((d.minTemp - weekMin) / weekRange) * 100;
                const widthPct = ((d.maxTemp - d.minTemp) / weekRange) * 100;
                return (
                  <View
                    key={i}
                    style={[
                      styles.weekRow,
                      i < weekDays.length - 1 && styles.weekRowBorder,
                    ]}
                  >
                    <View style={styles.weekDateCol}>
                      <Text style={styles.weekDate}>{d.date}</Text>
                      <Text style={styles.weekWeekday}>{d.weekday}</Text>
                    </View>
                    <Icon
                      name={icon}
                      size={22}
                      color={colors.primary}
                      style={styles.weekIcon}
                    />
                    <Text style={styles.weekMinTemp}>{d.minTemp}°</Text>
                    <View style={styles.weekTempBar}>
                      <View style={styles.weekTempTrack}>
                        <View
                          style={[
                            styles.weekTempFill,
                            {
                              left: `${leftPct}%`,
                              width: `${widthPct}%`,
                            },
                          ]}
                        />
                      </View>
                    </View>
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
    paddingVertical: spacingV2.xl,
  },
  bigTemp: {
    fontSize: 80,
    fontWeight: "200",
    color: colors.text,
    marginTop: spacingV2.sm,
    letterSpacing: -2,
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
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  chartCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.md,
    overflow: "hidden",
  },
  weekCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingVertical: spacingV2.md,
    paddingHorizontal: spacingV2.lg,
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
  weekDateCol: {
    width: 44,
  },
  weekDate: {
    fontSize: fontSizeV2.sm,
    color: colors.text,
    fontWeight: "600",
  },
  weekWeekday: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  weekIcon: {
    width: 28,
    textAlign: "center",
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
  weekTempBar: {
    flex: 1,
    height: 4,
    justifyContent: "center",
  },
  weekTempTrack: {
    height: 4,
    backgroundColor: colors.borderLight,
    borderRadius: 2,
    overflow: "hidden",
  },
  weekTempFill: {
    position: "absolute",
    height: 4,
    backgroundColor: colors.primaryLight,
    borderRadius: 2,
  },
  alertSection: {
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.xl,
  },
  alertBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
  },
  alertIconWrap: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  alertTextWrap: {
    flex: 1,
  },
  alertTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  alertDesc: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
});
