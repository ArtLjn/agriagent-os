import React, { useEffect, useMemo } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation } from "@react-navigation/native";
import dayjs from "dayjs";
import { useCostStore } from "../../stores/costStore";
import { useCycleStore } from "../../stores/cycleStore";
import { useAgentStore } from "../../stores/agentStore";
import { useSettingsStore } from "../../stores/settingsStore";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

const STAT_CARDS = [
  { key: "income", label: "本月收入", icon: "cash-plus", color: colors.income, bg: colors.surface },
  { key: "cost", label: "本月支出", icon: "cash-minus", color: colors.expense, bg: colors.surface },
  { key: "cycles", label: "活跃茬口", icon: "sprout", color: colors.primary, bg: colors.surface },
  { key: "days", label: "种植天数", icon: "calendar-clock", color: colors.aiPurple, bg: colors.surface },
];

function getFarmAge(cycles: { start_date: string }[]): number {
  if (cycles.length === 0) return 0;
  const earliest = new Date(
    Math.min(...cycles.map((c) => new Date(c.start_date).getTime()))
  );
  return Math.max(0, Math.floor((Date.now() - earliest.getTime()) / 86400000));
}

function getCurrentMonthStats(records: { record_type: string; amount: string; record_date: string }[]) {
  const currentMonth = dayjs().format("YYYY-MM");
  const monthRecords = records.filter((r) => r.record_date.startsWith(currentMonth));
  const income = monthRecords
    .filter((r) => r.record_type === "income")
    .reduce((sum, r) => sum + parseFloat(r.amount), 0);
  const cost = monthRecords
    .filter((r) => r.record_type === "cost")
    .reduce((sum, r) => sum + parseFloat(r.amount), 0);
  return { income, cost };
}

function getWeeklyTrend(records: { record_type: string; amount: string; record_date: string }[]) {
  const days: number[] = [];
  for (let i = 6; i >= 0; i--) {
    const d = dayjs().subtract(i, "day").format("YYYY-MM-DD");
    const dayCost = records
      .filter((r) => r.record_date === d && r.record_type === "cost")
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    days.push(dayCost);
  }
  const max = Math.max(...days, 1);
  return days.map((v) => ({ value: v, height: Math.max(4, (v / max) * 40) }));
}

const WEEKDAY_LABELS = ["一", "二", "三", "四", "五", "六", "日"];

export const FarmDashboardScreen: React.FC = () => {
  const navigation = useNavigation();
  const { records, fetchRecords } = useCostStore();
  const { cycles, fetchCycles } = useCycleStore();
  const { weather, cityName, fetchWeather } = useAgentStore();
  const { displayName } = useSettingsStore();

  useEffect(() => {
    fetchRecords();
    fetchCycles();
    fetchWeather();
  }, [fetchRecords, fetchCycles, fetchWeather]);

  const stats = useMemo(() => getCurrentMonthStats(records), [records]);
  const activeCycles = cycles.filter((c) => c.status === "active");
  const farmAge = getFarmAge(cycles);
  const weeklyTrend = useMemo(() => getWeeklyTrend(records), [records]);
  const recentRecords = records.slice(0, 5);

  const today = dayjs();
  const startOfWeek = today.startOf("week").add(1, "day");
  const weekDayIndex = today.day() === 0 ? 6 : today.day() - 1;

  const tempMax = weather?.daily?.temperature_2m_max?.[0] ?? "--";
  const tempMin = weather?.daily?.temperature_2m_min?.[0] ?? "--";
  const precip = weather?.daily?.precipitation_sum?.[0] ?? 0;
  const weatherDesc = precip > 5 ? "雨" : precip > 0 ? "阴" : "晴";
  const weatherIcon = precip > 5 ? "weather-pouring" : precip > 0 ? "weather-cloudy" : "white-balance-sunny";
  const weatherAccent = precip > 5 ? "#5B8DB8" : precip > 0 ? "#7A8B9A" : "#C9A03F";

  const statValues: Record<string, string> = {
    income: stats.income > 0 ? `+${stats.income.toFixed(0)}` : "0",
    cost: stats.cost > 0 ? `-${stats.cost.toFixed(0)}` : "0",
    cycles: String(activeCycles.length),
    days: String(farmAge),
  };

  return (
    <SafeAreaView style={styles.container} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity
            style={styles.backBtn}
            onPress={() => navigation.goBack()}
            activeOpacity={0.7}
          >
            <Icon name="arrow-left" size={22} color={colors.text} />
          </TouchableOpacity>
          <View style={styles.headerCenter}>
            <Text style={styles.headerTitle}>农场概览</Text>
            <Text style={styles.headerDate}>
              {today.format("YYYY年M月D日")} 星期{WEEKDAY_LABELS[weekDayIndex]}
            </Text>
          </View>
          <View style={styles.backBtn} />
        </View>

        {/* Weather Card */}
        <View style={styles.weatherCard}>
          <View style={styles.weatherLeft}>
            <Text style={styles.weatherCity}>{cityName}</Text>
            <Text style={styles.weatherTemp}>
              {tempMax}° / {tempMin}°
            </Text>
            <Text style={[styles.weatherDesc, { color: weatherAccent }]}>
              {weatherDesc}
            </Text>
          </View>
          <View style={[styles.weatherIconWrap, { borderColor: weatherAccent + "25" }]}>
            <Icon name={weatherIcon} size={28} color={weatherAccent} />
          </View>
        </View>

        {/* Stats Grid */}
        <View style={styles.statsGrid}>
          {STAT_CARDS.map((card) => (
            <View key={card.key} style={[styles.statCard, { backgroundColor: card.bg }]}>
              <View style={styles.statCardHeader}>
                <View style={[styles.statCardIcon, { backgroundColor: card.color + "15" }]}>
                  <Icon name={card.icon} size={16} color={card.color} />
                </View>
                <Text style={[styles.statCardValue, { color: card.color }]}>
                  {statValues[card.key]}
                </Text>
              </View>
              <Text style={styles.statCardLabel}>{card.label}</Text>
            </View>
          ))}
        </View>

        {/* Weekly Trend */}
        <View style={styles.sectionCard}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>近7天支出趋势</Text>
            <Text style={styles.sectionSubtitle}>
              本周共支出 ¥
              {weeklyTrend.reduce((s, d) => s + d.value, 0).toFixed(0)}
            </Text>
          </View>
          <View style={styles.chartRow}>
            {weeklyTrend.map((bar, i) => (
              <View key={i} style={styles.barColumn}>
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.barFill,
                      {
                        height: bar.height,
                        backgroundColor:
                          i === weekDayIndex ? colors.primary : colors.primary + "40",
                      },
                    ]}
                  />
                </View>
                <Text
                  style={[
                    styles.barLabel,
                    i === weekDayIndex && { color: colors.primary, fontWeight: "700" },
                  ]}
                >
                  {WEEKDAY_LABELS[(startOfWeek.day() + i - 1) % 7]}
                </Text>
              </View>
            ))}
          </View>
        </View>

        {/* Active Crops */}
        {activeCycles.length > 0 && (
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>活跃作物</Text>
            <View style={styles.cropList}>
              {activeCycles.map((cycle) => {
                const days = getFarmAge([cycle]);
                return (
                  <View key={cycle.id} style={styles.cropItem}>
                    <View style={styles.cropHeader}>
                      <Text style={styles.cropName}>{cycle.name}</Text>
                      <View style={styles.cropBadge}>
                        <Text style={styles.cropBadgeText}>{cycle.current_stage_name || "进行中"}</Text>
                      </View>
                    </View>
                    <Text style={styles.cropMeta}>
                      {cycle.crop_template_name} · 已种植 {days} 天
                    </Text>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        {/* Recent Activity */}
        {recentRecords.length > 0 && (
          <View style={styles.sectionCard}>
            <Text style={styles.sectionTitle}>近期动态</Text>
            <View style={styles.activityList}>
              {recentRecords.map((record) => {
                const isCost = record.record_type === "cost";
                return (
                  <View key={record.id} style={styles.activityItem}>
                    <View
                      style={[
                        styles.activityDot,
                        {
                          backgroundColor: isCost ? colors.danger : colors.success,
                        },
                      ]}
                    />
                    <View style={styles.activityBody}>
                      <View style={styles.activityRow}>
                        <Text style={styles.activityCategory}>{record.category}</Text>
                        <Text
                          style={[
                            styles.activityAmount,
                            { color: isCost ? colors.danger : colors.success },
                          ]}
                        >
                          {isCost ? "-" : "+"}
                          {record.amount}
                        </Text>
                      </View>
                      <Text style={styles.activityDate}>
                        {dayjs(record.record_date).format("M月D日")}
                        {record.note ? ` · ${record.note}` : ""}
                      </Text>
                    </View>
                  </View>
                );
              })}
            </View>
          </View>
        )}

        <View style={{ height: spacingV2.xxxl }} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    padding: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.xl,
  },
  backBtn: {
    width: 36,
    height: 36,
    borderRadius: borderRadiusV2.md,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  headerCenter: {
    alignItems: "center",
  },
  headerTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
  },
  headerDate: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  weatherCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  weatherLeft: {
    gap: 2,
  },
  weatherCity: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  weatherTemp: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    letterSpacing: -0.5,
  },
  weatherDesc: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },
  weatherIconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  statCard: {
    width: "47%",
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    gap: spacingV2.sm,
  },
  statCardHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  statCardIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  statCardValue: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  statCardLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  sectionCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  sectionTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  sectionSubtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  chartRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    height: 60,
    paddingHorizontal: spacingV2.sm,
  },
  barColumn: {
    alignItems: "center",
    gap: 6,
    flex: 1,
  },
  barTrack: {
    width: 6,
    height: 40,
    backgroundColor: "transparent",
    borderRadius: 3,
    justifyContent: "flex-end",
    overflow: "hidden",
  },
  barFill: {
    width: "100%",
    borderRadius: 3,
  },
  barLabel: {
    fontSize: 11,
    color: colors.textTertiary,
  },
  cropList: {
    gap: spacingV2.md,
  },
  cropItem: {
    backgroundColor: colors.background,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.md,
    gap: 4,
  },
  cropHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cropName: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  cropBadge: {
    backgroundColor: colors.successMuted,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.sm,
  },
  cropBadgeText: {
    fontSize: 11,
    fontWeight: "600",
    color: colors.success,
  },
  cropMeta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  activityList: {
    gap: spacingV2.md,
  },
  activityItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.md,
  },
  activityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginTop: 6,
  },
  activityBody: {
    flex: 1,
    gap: 2,
  },
  activityRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  activityCategory: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  activityAmount: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
  },
  activityDate: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
});
