import React, { useEffect, useMemo, useState } from "react";
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
import { costApi, plantingApi } from "../../api/client";
import type { CostRecord, WorkerSummaryItem } from "../../api/types";
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
  const [laborRecords, setLaborRecords] = useState<CostRecord[]>([]);
  const [cycleWorkers, setCycleWorkers] = useState<WorkerSummaryItem[]>([]);
  const {
    currentCycle,
    loading,
    units,
    operationTypes,
    fetchCycleDetail,
    fetchUnits,
    fetchOperationTypes,
  } = useCycleStore();

  useEffect(() => {
    fetchCycleDetail(cycleId);
    fetchUnits(cycleId);
  }, [cycleId, fetchCycleDetail, fetchUnits]);

  useEffect(() => {
    costApi
      .getRecords({ cycle_id: cycleId, category: "人工" })
      .then((res) => setLaborRecords((res.data as any)?.items ?? res.data ?? []))
      .catch(() => setLaborRecords([]));
    plantingApi
      .getWorkerSummary()
      .then((res) => {
        setCycleWorkers(
          (res.data.items || []).filter((worker) =>
            worker.cycle_summaries.some((cycle) => cycle.cycle_id === cycleId)
          )
        );
      })
      .catch(() => setCycleWorkers([]));
  }, [cycleId]);

  useEffect(() => {
    if (currentCycle?.name) {
      fetchOperationTypes(currentCycle.name);
    }
  }, [currentCycle?.name, fetchOperationTypes]);

  const laborSummary = useMemo(() => {
    const totalCost = laborRecords.reduce(
      (sum, record) => sum + Number(record.amount || 0),
      0
    );
    const totalUnpaid = cycleWorkers.reduce((sum, worker) => {
      const cycle = worker.cycle_summaries.find(
        (item) => item.cycle_id === cycleId
      );
      return sum + Number(cycle?.total_unpaid || 0);
    }, 0);
    return {
      totalCost,
      totalUnpaid,
      workers: cycleWorkers.map((worker) => worker.name).slice(0, 3),
    };
  }, [cycleId, laborRecords, cycleWorkers]);

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
            <Icon name="map-marker-radius" size={18} color={colors.primary} />
            <Text style={styles.infoCellLabel}>面积/单元</Text>
            <Text style={styles.infoCellValue} numberOfLines={1}>
              {currentCycle.total_area_mu
                ? `${Number(currentCycle.total_area_mu).toFixed(2).replace(/\.00$/, "")}亩`
                : currentCycle.field_name || "未指定"}
              {currentCycle.unit_count ? ` · ${currentCycle.unit_count}个` : ""}
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

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>种植单元</Text>
        <View style={styles.unitCard}>
          {units.length > 0 ? (
            units.map((unit) => (
              <View key={unit.id} style={styles.unitRow}>
                <View style={styles.unitIcon}>
                  <Icon name="greenhouse" size={18} color={colors.primary} />
                </View>
                <View style={styles.unitInfo}>
                  <Text style={styles.unitName}>{unit.name}</Text>
                  <Text style={styles.unitMeta}>
                    {unit.area_mu ? `${Number(unit.area_mu).toFixed(2).replace(/\.00$/, "")} 亩` : "未填面积"}
                    {unit.status ? ` · ${unit.status}` : ""}
                  </Text>
                </View>
              </View>
            ))
          ) : (
            <Text style={styles.emptyHint}>
              暂未拆分棚或地块，当前仍按批次整体管理。
            </Text>
          )}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>作业快捷项</Text>
        <View style={styles.operationWrap}>
          {operationTypes.slice(0, 8).map((item) => (
            <View key={item.name} style={styles.operationPill}>
              <Text style={styles.operationText}>{item.name}</Text>
            </View>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeaderRow}>
          <Text style={styles.sectionTitle}>本茬用工</Text>
          <TouchableOpacity
            onPress={() =>
              navigation.navigate("CostList", {
                filters: {
                  cycleId,
                  category: "人工",
                  title: `${currentCycle.name}人工账单`,
                },
              })
            }
          >
            <Text style={styles.sectionLink}>查看人工账单</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.laborCard}>
          <View style={styles.laborMetricRow}>
            <View style={styles.laborMetric}>
              <Text style={styles.laborLabel}>人工支出</Text>
              <Text style={styles.laborValue}>
                {laborSummary.totalCost.toFixed(0)}
              </Text>
            </View>
            <View style={styles.laborMetric}>
              <Text style={styles.laborLabel}>未结金额</Text>
              <Text style={[styles.laborValue, { color: colors.danger }]}>
                {laborSummary.totalUnpaid.toFixed(0)}
              </Text>
            </View>
            <View style={styles.laborMetric}>
              <Text style={styles.laborLabel}>相关工人</Text>
              <Text style={styles.laborValue}>{cycleWorkers.length}</Text>
            </View>
          </View>
          <Text style={styles.laborWorkers} numberOfLines={1}>
            {laborSummary.workers.length > 0
              ? laborSummary.workers.join("、")
              : "暂无本茬工资记录"}
          </Text>
          <View style={styles.laborActions}>
            <TouchableOpacity
              style={styles.laborActionPrimary}
              onPress={() =>
                navigation.navigate("WageCreate", {
                  cycleId,
                  cropName: currentCycle.name,
                })
              }
            >
              <Icon name="cash-plus" size={18} color={colors.primary} />
              <Text style={styles.laborActionPrimaryText}>记工资</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.laborActionSecondary}
              onPress={() =>
                navigation.navigate("CostList", {
                  filters: {
                    cycleId,
                    category: "人工",
                    title: `${currentCycle.name}人工账单`,
                  },
                })
              }
            >
              <Text style={styles.laborActionSecondaryText}>查看账单</Text>
            </TouchableOpacity>
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
          onPress={() =>
            navigation.navigate("WorkOrderCreate" as never, {
              cycleId,
              cropName: currentCycle.name,
            } as never)
          }
          activeOpacity={0.7}
        >
          <View
            style={[
              styles.actionIcon,
              { backgroundColor: colors.primaryMuted },
            ]}
          >
            <Icon name="clipboard-plus" size={20} color={colors.primary} />
          </View>
          <Text style={styles.actionLabel}>记录作业</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionBtn}
          onPress={() =>
            navigation.navigate("PlantingUnits" as never, { cycleId } as never)
          }
          activeOpacity={0.7}
        >
          <View
            style={[
              styles.actionIcon,
              { backgroundColor: "rgba(59, 178, 115, 0.08)" },
            ]}
          >
            <Icon name="greenhouse" size={20} color={colors.success} />
          </View>
          <Text style={styles.actionLabel}>种植单元</Text>
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
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  sectionLink: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "800",
  },
  laborCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  laborMetricRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  laborMetric: {
    flex: 1,
    minHeight: 68,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.background,
    padding: spacingV2.md,
    justifyContent: "center",
  },
  laborLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  laborValue: {
    marginTop: 4,
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "900",
  },
  laborWorkers: {
    marginTop: spacingV2.md,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  laborActions: {
    flexDirection: "row",
    gap: spacingV2.md,
    marginTop: spacingV2.lg,
  },
  laborActionPrimary: {
    flex: 1,
    minHeight: 44,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacingV2.xs,
  },
  laborActionPrimaryText: {
    fontSize: fontSizeV2.md,
    color: colors.primary,
    fontWeight: "800",
  },
  laborActionSecondary: {
    flex: 1,
    minHeight: 44,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.surfaceMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  laborActionSecondaryText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "800",
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
  unitCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacingV2.sm,
    gap: spacingV2.md,
  },
  unitIcon: {
    width: 36,
    height: 36,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
  },
  unitInfo: {
    flex: 1,
    minWidth: 0,
  },
  unitName: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
  },
  unitMeta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  emptyHint: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
    paddingVertical: spacingV2.sm,
  },
  operationWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
  },
  operationPill: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.primaryMuted,
  },
  operationText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.primary,
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
