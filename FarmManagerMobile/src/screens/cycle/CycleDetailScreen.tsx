import React, { useEffect } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
} from "react-native";
import {
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { useCycleStore } from "../../stores/cycleStore";
import { Timeline } from "../../components/Timeline";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type RouteParams = RouteProp<RootStackParamList, "CycleDetail">;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const STATUS_MAP: Record<
  string,
  { label: string; color: string; bgColor: string }
> = {
  active: {
    label: "进行中",
    color: colors.success,
    bgColor: "rgba(59, 178, 115, 0.10)",
  },
  completed: {
    label: "已完成",
    color: colors.info,
    bgColor: "rgba(91, 141, 184, 0.10)",
  },
  abandoned: {
    label: "已废弃",
    color: colors.danger,
    bgColor: "rgba(196, 91, 91, 0.10)",
  },
};

function getCropEmoji(name: string): string {
  if (name.includes("西瓜")) return "🍉";
  if (name.includes("辣椒")) return "🌶️";
  if (name.includes("番茄") || name.includes("西红柿")) return "🍅";
  if (name.includes("黄瓜")) return "🥒";
  if (name.includes("茄子")) return "🍆";
  if (name.includes("白菜")) return "🥬";
  if (name.includes("玉米")) return "🌽";
  if (name.includes("土豆")) return "🥔";
  if (name.includes("萝卜")) return "🥕";
  if (name.includes("南瓜")) return "🎃";
  if (name.includes("大蒜") || name.includes("洋葱")) return "🧄";
  return "🌱";
}

export const CycleDetailScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { currentCycle, loading, fetchCycleDetail } = useCycleStore();

  useEffect(() => {
    fetchCycleDetail(cycleId);
  }, [cycleId, fetchCycleDetail]);

  if (loading || !currentCycle) {
    return <Loading />;
  }

  const status = STATUS_MAP[currentCycle.status] || {
    label: currentCycle.status,
    color: colors.textSecondary,
    bgColor: colors.surfaceMuted,
  };

  const timelineItems = currentCycle.stages.map((stage) => ({
    id: String(stage.id),
    title: stage.name,
    subtitle: stage.key_tasks || "无关键任务",
    dateRange: `${stage.start_date} ~ ${stage.end_date}`,
    isCurrent: stage.is_current,
  }));

  const currentStage = currentCycle.stages.find((s) => s.is_current);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      {/* Hero */}
      <View style={styles.hero}>
        <Text style={styles.heroEmoji}>
          {getCropEmoji(currentCycle.name)}
        </Text>
        <Text style={styles.heroTitle}>{currentCycle.name}</Text>
        <View style={[styles.statusPill, { backgroundColor: status.bgColor }]}>
          <View
            style={[styles.statusDot, { backgroundColor: status.color }]}
          />
          <Text style={[styles.statusText, { color: status.color }]}>
            {status.label}
          </Text>
        </View>
      </View>

      {/* Info Grid */}
      <View style={styles.infoCard}>
        <View style={styles.infoGrid}>
          <View style={styles.infoCell}>
            <Icon name="map-marker" size={18} color={colors.primary} />
            <Text style={styles.infoCellLabel}>地块</Text>
            <Text style={styles.infoCellValue} numberOfLines={1}>
              {currentCycle.field_name || "未指定"}
            </Text>
          </View>
          <View style={[styles.infoCell, styles.infoCellBorder]}>
            <Icon name="calendar" size={18} color={colors.primary} />
            <Text style={styles.infoCellLabel}>开始日期</Text>
            <Text style={styles.infoCellValue}>
              {currentCycle.start_date}
            </Text>
          </View>
          <View style={[styles.infoCell, styles.infoCellBorderTop]}>
            <Icon
              name="format-list-numbered"
              size={18}
              color={colors.primary}
            />
            <Text style={styles.infoCellLabel}>阶段数</Text>
            <Text style={styles.infoCellValue}>
              {currentCycle.stages.length} 个
            </Text>
          </View>
          <View
            style={[
              styles.infoCell,
              styles.infoCellBorder,
              styles.infoCellBorderTop,
            ]}
          >
            <Icon name="progress-clock" size={18} color={colors.primary} />
            <Text style={styles.infoCellLabel}>当前阶段</Text>
            <Text style={styles.infoCellValue} numberOfLines={1}>
              {currentStage?.name || "-"}
            </Text>
          </View>
        </View>
      </View>

      {/* Timeline */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>生长阶段</Text>
        <View style={styles.timelineCard}>
          <Timeline items={timelineItems} />
        </View>
      </View>

      {/* Actions */}
      <View style={styles.actions}>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => navigation.navigate("LogList" as never, { cycleId } as never)}
          activeOpacity={0.7}
        >
          <View
            style={[
              styles.actionIcon,
              { backgroundColor: colors.primaryMuted },
            ]}
          >
            <Icon name="clipboard-text" size={20} color={colors.primary} />
          </View>
          <Text style={styles.actionLabel}>农事记录</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => navigation.navigate("Profit" as never, { cycleId } as never)}
          activeOpacity={0.7}
        >
          <View
            style={[
              styles.actionIcon,
              { backgroundColor: "rgba(59, 178, 115, 0.08)" },
            ]}
          >
            <Icon name="chart-line" size={20} color={colors.success} />
          </View>
          <Text style={styles.actionLabel}>利润统计</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() => navigation.navigate("AgentChat" as never, { cycleId } as never)}
          activeOpacity={0.7}
        >
          <View
            style={[
              styles.actionIcon,
              { backgroundColor: colors.aiPurpleMuted },
            ]}
          >
            <Icon name="robot" size={20} color={colors.aiPurple} />
          </View>
          <Text style={styles.actionLabel}>农事顾问</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: spacingV2.xxxl },
  hero: {
    alignItems: "center",
    paddingVertical: spacingV2.xxl,
    paddingHorizontal: spacingV2.lg,
  },
  heroEmoji: {
    fontSize: 48,
    marginBottom: spacingV2.md,
  },
  heroTitle: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "800",
    color: colors.text,
    textAlign: "center",
    marginBottom: spacingV2.md,
    letterSpacing: -0.5,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.xs,
    borderRadius: borderRadiusV2.full,
    gap: spacingV2.xs,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
  },
  infoCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.xl,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  infoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  infoCell: {
    width: "50%",
    alignItems: "center",
    paddingVertical: spacingV2.xl,
    paddingHorizontal: spacingV2.md,
  },
  infoCellBorder: {
    borderLeftWidth: 1,
    borderLeftColor: colors.borderLight,
  },
  infoCellBorderTop: {
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  infoCellLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: spacingV2.sm,
    marginBottom: spacingV2.xs,
  },
  infoCellValue: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  section: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.xl,
  },
  sectionTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.md,
  },
  timelineCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxxl,
    paddingTop: spacingV2.lg,
    paddingBottom: spacingV2.md,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.xl,
  },
  actionBtn: {
    alignItems: "center",
    width: 80,
  },
  actionIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.sm,
  },
  actionLabel: {
    fontSize: 13,
    color: colors.text,
    fontWeight: "500",
  },
});
