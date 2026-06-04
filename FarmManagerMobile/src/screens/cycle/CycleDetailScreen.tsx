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
  if (name.includes("西瓜")) {
    return "🍉";
  }
  if (name.includes("辣椒")) {
    return "🌶️";
  }
  if (name.includes("番茄") || name.includes("西红柿")) {
    return "🍅";
  }
  if (name.includes("黄瓜")) {
    return "🥒";
  }
  if (name.includes("茄子")) {
    return "🍆";
  }
  if (name.includes("白菜")) {
    return "🥬";
  }
  if (name.includes("玉米")) {
    return "🌽";
  }
  if (name.includes("土豆")) {
    return "🥔";
  }
  if (name.includes("萝卜")) {
    return "🥕";
  }
  if (name.includes("南瓜")) {
    return "🎃";
  }
  if (name.includes("大蒜") || name.includes("洋葱")) {
    return "🧄";
  }
  return "🌱";
}

function parseDateValue(value: string): number {
  const parsed = new Date(`${value}T00:00:00`).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}

function getTodayValue(): number {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
}

function getStageStatus(stage: { start_date: string; end_date: string }) {
  const today = getTodayValue();
  const start = parseDateValue(stage.start_date);
  const end = parseDateValue(stage.end_date);
  if (start && today < start) return "upcoming";
  if (end && today > end) return "done";
  return "current";
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

  const stageItems = currentCycle.stages.map((stage, index) => ({
    ...stage,
    status: getStageStatus(stage),
    index,
  }));
  const currentStage =
    stageItems.find((stage) => stage.status === "current") ||
    stageItems.find((stage) => stage.is_current) ||
    stageItems[0];
  const currentStageIndex = currentStage?.index ?? 0;
  const nextStage = stageItems.find((stage) => stage.index > currentStageIndex);
  const progressPercent =
    stageItems.length > 1
      ? Math.round((currentStageIndex / (stageItems.length - 1)) * 100)
      : 0;
  const areaText = currentCycle.total_area_mu
    ? `${Number(currentCycle.total_area_mu).toFixed(2).replace(/\.00$/, "")} 亩`
    : currentCycle.field_name || "未填面积";
  const unitCountText = currentCycle.unit_count
    ? `${currentCycle.unit_count} 个单元`
    : "按整茬管理";
  const seasonText = currentCycle.season || "当前批次";
  const quickOperations = operationTypes.slice(0, 4);
  const previewUnits = units.slice(0, 4);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.summaryCard}>
        <View style={styles.summaryTop}>
          <View style={styles.cropIcon}>
            <Text style={styles.cropEmoji}>
              {getCropEmoji(currentCycle.name)}
            </Text>
          </View>
          <View style={styles.summaryText}>
            <Text style={styles.batchLabel}>{seasonText}</Text>
            <Text style={styles.heroTitle} numberOfLines={2}>
              {currentCycle.name}
            </Text>
            <Text style={styles.heroMeta} numberOfLines={1}>
              {areaText} · {unitCountText} · {currentStage?.name || "未开始"}
            </Text>
          </View>
          <View
            style={[styles.statusPill, { backgroundColor: status.bgColor }]}
          >
            <View
              style={[styles.statusDot, { backgroundColor: status.color }]}
            />
            <Text style={[styles.statusText, { color: status.color }]}>
              {status.label}
            </Text>
          </View>
        </View>

        <View style={styles.summaryStats}>
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{areaText}</Text>
            <Text style={styles.statLabel}>种植面积</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{unitCountText}</Text>
            <Text style={styles.statLabel}>管理范围</Text>
          </View>
          <View style={styles.statDivider} />
          <View style={styles.statItem}>
            <Text style={styles.statValue}>{currentCycle.start_date}</Text>
            <Text style={styles.statLabel}>开始日期</Text>
          </View>
        </View>
      </View>

      <View style={styles.quickPanel}>
        <TouchableOpacity
          style={styles.primaryAction}
          onPress={() =>
            navigation.navigate(
              "WorkOrderCreate" as never,
              {
                cycleId,
                cropName: currentCycle.name,
              } as never
            )
          }
          activeOpacity={0.82}
        >
          <Icon name="clipboard-plus" size={22} color={colors.textInverse} />
          <View style={styles.primaryActionText}>
            <Text style={styles.primaryActionTitle}>记一条农事</Text>
            <Text style={styles.primaryActionSub}>
              授粉、压蔓、采收、用工一起记
            </Text>
          </View>
          <Icon name="chevron-right" size={22} color={colors.textInverse} />
        </TouchableOpacity>

        <View style={styles.secondaryActions}>
          <TouchableOpacity
            style={styles.secondaryAction}
            onPress={() =>
              navigation.navigate("LogList" as never, { cycleId } as never)
            }
            activeOpacity={0.75}
          >
            <Icon
              name="clipboard-text-clock"
              size={20}
              color={colors.primary}
            />
            <Text style={styles.secondaryActionText}>看记录</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryAction}
            onPress={() =>
              navigation.navigate(
                "PlantingUnits" as never,
                { cycleId } as never
              )
            }
            activeOpacity={0.75}
          >
            <Icon name="greenhouse" size={20} color={colors.success} />
            <Text style={styles.secondaryActionText}>棚/地块</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryAction}
            onPress={() =>
              navigation.navigate("Profit" as never, { cycleId } as never)
            }
            activeOpacity={0.75}
          >
            <Icon name="chart-line" size={20} color={colors.success} />
            <Text style={styles.secondaryActionText}>利润</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>棚 / 地块</Text>
          <TouchableOpacity
            onPress={() =>
              navigation.navigate(
                "PlantingUnits" as never,
                { cycleId } as never
              )
            }
          >
            <Text style={styles.sectionLink}>管理</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.unitCard}>
          {previewUnits.length > 0 ? (
            previewUnits.map((unit) => (
              <View key={unit.id} style={styles.unitRow}>
                <View style={styles.unitIcon}>
                  <Icon name="greenhouse" size={18} color={colors.primary} />
                </View>
                <View style={styles.unitInfo}>
                  <Text style={styles.unitName}>{unit.name}</Text>
                  <Text style={styles.unitMeta}>
                    {unit.area_mu
                      ? `${Number(unit.area_mu)
                          .toFixed(2)
                          .replace(/\.00$/, "")} 亩`
                      : "未填面积"}
                    {unit.status ? ` · ${unit.status}` : ""}
                  </Text>
                </View>
              </View>
            ))
          ) : (
            <Text style={styles.emptyHint}>
              还没拆棚或地块，也可以先按整茬记录农事。
            </Text>
          )}
          {units.length > previewUnits.length ? (
            <Text style={styles.moreHint}>
              还有 {units.length - previewUnits.length} 个，点“管理”查看
            </Text>
          ) : null}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>常用作业</Text>
        <View style={styles.operationWrap}>
          {quickOperations.map((item) => (
            <TouchableOpacity
              key={item.name}
              style={styles.operationPill}
              onPress={() =>
                navigation.navigate(
                  "WorkOrderCreate" as never,
                  {
                    cycleId,
                    cropName: currentCycle.name,
                    operationType: item.name,
                  } as never
                )
              }
            >
              <Text style={styles.operationText}>{item.name}</Text>
            </TouchableOpacity>
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

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>生长阶段</Text>
          <Text style={styles.sectionMeta}>
            {currentStageIndex + 1}/{stageItems.length}
          </Text>
        </View>
        <View style={styles.stageCard}>
          <View style={styles.stageTop}>
            <View style={styles.stageBadge}>
              <Icon name="sprout" size={18} color={colors.success} />
            </View>
            <View style={styles.stageCopy}>
              <Text style={styles.stageEyebrow}>今天应处于</Text>
              <Text style={styles.stageTitle}>{currentStage?.name || "-"}</Text>
              <Text style={styles.stageDesc} numberOfLines={2}>
                {currentStage?.key_tasks || "按当前作物模板继续日常管理"}
              </Text>
            </View>
          </View>

          <View style={styles.progressTrack}>
            <View
              style={[styles.progressFill, { width: `${progressPercent}%` }]}
            />
          </View>

          <View style={styles.stageRail}>
            {stageItems.map((stage) => {
              const isCurrent = stage.index === currentStageIndex;
              const isDone = stage.status === "done";
              return (
                <View key={stage.id} style={styles.stageRailItem}>
                  <View
                    style={[
                      styles.stageDot,
                      isDone && styles.stageDotDone,
                      isCurrent && styles.stageDotCurrent,
                    ]}
                  />
                  <Text
                    style={[
                      styles.stageRailText,
                      isCurrent && styles.stageRailTextCurrent,
                    ]}
                    numberOfLines={1}
                  >
                    {stage.name}
                  </Text>
                </View>
              );
            })}
          </View>

          <View style={styles.stageFooter}>
            <View>
              <Text style={styles.stageFooterLabel}>当前阶段日期</Text>
              <Text style={styles.stageFooterValue}>
                {currentStage?.start_date || "-"} 至{" "}
                {currentStage?.end_date || "-"}
              </Text>
            </View>
            <View style={styles.nextStageBox}>
              <Text style={styles.nextStageLabel}>下一阶段</Text>
              <Text style={styles.nextStageValue} numberOfLines={1}>
                {nextStage?.name || "暂无"}
              </Text>
            </View>
          </View>
        </View>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: {
    padding: spacingV2.md,
    paddingBottom: spacingV2.xxxl,
  },
  summaryCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.md,
    marginBottom: spacingV2.md,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 14,
    elevation: 2,
  },
  summaryTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.md,
  },
  cropIcon: {
    width: 52,
    height: 52,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
  },
  cropEmoji: { fontSize: 28 },
  summaryText: { flex: 1, minWidth: 0 },
  batchLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.success,
    marginBottom: spacingV2.xs,
  },
  heroTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
    lineHeight: 28,
  },
  heroMeta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: spacingV2.xs,
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
  summaryStats: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacingV2.lg,
    paddingTop: spacingV2.lg,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  statItem: { flex: 1, minWidth: 0 },
  statValue: {
    fontSize: fontSizeV2.md,
    fontWeight: "800",
    color: colors.text,
  },
  statLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  statDivider: {
    width: 1,
    height: 30,
    backgroundColor: colors.borderLight,
    marginHorizontal: spacingV2.md,
  },
  quickPanel: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.sm,
    marginBottom: spacingV2.xl,
  },
  primaryAction: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 64,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.primary,
    gap: spacingV2.md,
  },
  primaryActionText: { flex: 1 },
  primaryActionTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "800",
    color: colors.textInverse,
  },
  primaryActionSub: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255, 255, 255, 0.82)",
    marginTop: 2,
  },
  secondaryActions: {
    flexDirection: "row",
    gap: spacingV2.sm,
    marginTop: spacingV2.sm,
  },
  secondaryAction: {
    flex: 1,
    minHeight: 48,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacingV2.xs,
  },
  secondaryActionText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.text,
  },
  section: {
    marginBottom: spacingV2.lg,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
  },
  sectionHeaderRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.md,
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
  sectionTitle: {
    fontSize: fontSizeV2.lg,
    fontWeight: "800",
    color: colors.text,
    marginBottom: 0,
  },
  sectionMeta: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: colors.textTertiary,
  },
  sectionLink: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.primary,
  },
  stageCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
  },
  stageTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.md,
  },
  stageBadge: {
    width: 44,
    height: 44,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.successMuted,
  },
  stageCopy: { flex: 1, minWidth: 0 },
  stageEyebrow: {
    fontSize: fontSizeV2.xs,
    fontWeight: "800",
    color: colors.success,
    marginBottom: 2,
  },
  stageTitle: {
    fontSize: fontSizeV2.xl,
    fontWeight: "800",
    color: colors.text,
  },
  stageDesc: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
    marginTop: spacingV2.xs,
  },
  progressTrack: {
    height: 8,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.borderLight,
    overflow: "hidden",
    marginTop: spacingV2.lg,
  },
  progressFill: {
    height: "100%",
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.success,
  },
  stageRail: {
    flexDirection: "row",
    gap: spacingV2.sm,
    marginTop: spacingV2.md,
  },
  stageRailItem: {
    flex: 1,
    minWidth: 0,
    alignItems: "center",
  },
  stageDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.border,
    marginBottom: spacingV2.xs,
  },
  stageDotDone: {
    backgroundColor: colors.success,
  },
  stageDotCurrent: {
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: colors.primary,
    marginTop: -2,
  },
  stageRailText: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    maxWidth: 64,
  },
  stageRailTextCurrent: {
    fontWeight: "800",
    color: colors.primary,
  },
  stageFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
    marginTop: spacingV2.lg,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  stageFooterLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  stageFooterValue: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.text,
  },
  nextStageBox: {
    maxWidth: 120,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    backgroundColor: colors.background,
  },
  nextStageLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  nextStageValue: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: colors.text,
  },
  unitCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
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
  moreHint: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.primary,
    paddingTop: spacingV2.sm,
  },
  operationWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacingV2.sm,
  },
  operationPill: {
    minHeight: 44,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(74, 123, 247, 0.16)",
  },
  operationText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.primary,
  },
});
