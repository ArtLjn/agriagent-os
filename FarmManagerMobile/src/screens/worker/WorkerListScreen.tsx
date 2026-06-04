import React, { useCallback, useMemo, useState } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { plantingApi } from "../../api/client";
import type {
  UnsettledLaborSummary,
  Worker,
  WorkerSummaryItem,
  WorkerSummaryResponse,
} from "../../api/types";
import { BigButton } from "../../components/BigButton";
import { EmptyState } from "../../components/EmptyState";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../theme/spacing";

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

function toNumber(value?: string | number | null): number {
  const parsed = Number(String(value ?? "0").replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMoney(value?: string | number | null): string {
  return toNumber(value).toFixed(0);
}

function getInitial(name: string): string {
  return name.trim().slice(0, 1) || "工";
}

function buildFallbackSummary(
  workers: Worker[],
  unsettled?: UnsettledLaborSummary | null
): WorkerSummaryResponse {
  const unsettledMap = new Map(
    (unsettled?.workers || []).map((item) => [
      item.worker_name,
      {
        unpaid: item.unpaid_amount,
        count: item.entry_count,
      },
    ])
  );

  const items = workers.map<WorkerSummaryItem>((worker) => {
    const debt = unsettledMap.get(worker.name);
    const unpaid = formatMoney(debt?.unpaid || 0);
    return {
      id: worker.id,
      name: worker.name,
      phone: worker.phone,
      default_pay_type: worker.default_pay_type,
      default_unit_price: worker.default_unit_price,
      total_payable: unpaid,
      total_paid: "0",
      total_unpaid: unpaid,
      entry_count: debt?.count || 0,
      cycle_summaries: [],
    };
  });

  return {
    items,
    total: items.length,
    total_payable: String(items.reduce((sum, item) => sum + toNumber(item.total_payable), 0)),
    total_paid: "0",
    total_unpaid: String(toNumber(unsettled?.total_unpaid)),
  };
}

export const WorkerListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const [summary, setSummary] = useState<WorkerSummaryResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [fallbackNote, setFallbackNote] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setFallbackNote(null);
    try {
      const res = await plantingApi.getWorkerSummary();
      setSummary(res.data);
    } catch {
      try {
        const [workersRes, unsettledRes] = await Promise.all([
          plantingApi.getWorkers(),
          plantingApi.getUnsettledLaborSummary().catch(() => ({ data: null })),
        ]);
        setSummary(buildFallbackSummary(workersRes.data, unsettledRes.data));
        setFallbackNote("后端工人汇总接口未就绪，当前使用工人档案和未结摘要展示。");
      } catch (err: any) {
        setFallbackNote(err.message || "工人数据加载失败");
        setSummary({ items: [], total: 0, total_payable: "0", total_paid: "0", total_unpaid: "0" });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData])
  );

  const workers = summary?.items || [];
  const filteredWorkers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return workers;
    }
    return workers.filter((worker) =>
      [worker.name, worker.phone, worker.default_unit_price]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized))
    );
  }, [query, workers]);

  const overview = useMemo(() => {
    const payable =
      summary?.total_payable ??
      workers.reduce((sum, item) => sum + toNumber(item.total_payable), 0);
    const paid =
      summary?.total_paid ??
      workers.reduce((sum, item) => sum + toNumber(item.total_paid), 0);
    const unpaid =
      summary?.total_unpaid ??
      workers.reduce((sum, item) => sum + toNumber(item.total_unpaid), 0);
    const cycleIds = new Set(
      workers.flatMap((item) =>
        item.cycle_summaries.map((cycle) => cycle.cycle_id)
      )
    );
    return {
      payable: formatMoney(payable),
      paid: formatMoney(paid),
      unpaid: formatMoney(unpaid),
      workers: summary?.total ?? workers.length,
      cycles: cycleIds.size,
    };
  }, [summary, workers]);

  const recentCycles = useMemo(() => {
    const cycles = workers.flatMap((worker) =>
      worker.cycle_summaries.map((cycle) => ({
        ...cycle,
        workerName: worker.name,
      }))
    );
    return cycles
      .sort((a, b) => String(b.recent_work_date || "").localeCompare(String(a.recent_work_date || "")))
      .slice(0, 4);
  }, [workers]);

  const openLedger = () => {
    navigation.navigate("CostList", {
      filters: {
        category: "人工",
        sourceType: "labor_entry",
        title: "人工工资账单",
      },
    });
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={loading}
          onRefresh={loadData}
          tintColor={colors.primary}
        />
      }
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View>
            <Text style={styles.heroLabel}>全场人工</Text>
            <Text style={styles.heroValue}>未结 {overview.unpaid} 元</Text>
          </View>
          <TouchableOpacity style={styles.heroIcon} onPress={openLedger}>
            <Icon name="receipt-text-outline" size={22} color={colors.textInverse} />
          </TouchableOpacity>
        </View>
        <View style={styles.metricRow}>
          <View style={styles.metricItem}>
            <Text style={styles.metricValue}>{overview.workers}</Text>
            <Text style={styles.metricLabel}>工人</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricValue}>{overview.cycles}</Text>
            <Text style={styles.metricLabel}>相关茬口</Text>
          </View>
          <View style={styles.metricItem}>
            <Text style={styles.metricValue}>{overview.payable}</Text>
            <Text style={styles.metricLabel}>应付</Text>
          </View>
        </View>
      </View>

      <View style={styles.actionRow}>
        <BigButton
          title="记一笔工资"
          icon="cash-plus"
          onPress={() => navigation.navigate("WageCreate", {})}
          style={styles.actionButton}
        />
        <TouchableOpacity style={styles.outlineButton} onPress={openLedger}>
          <Icon name="filter-variant" size={18} color={colors.textSecondary} />
          <Text style={styles.outlineText}>查人工账单</Text>
        </TouchableOpacity>
      </View>

      {fallbackNote ? (
        <View style={styles.notice}>
          <Icon name="information-outline" size={16} color={colors.info} />
          <Text style={styles.noticeText}>{fallbackNote}</Text>
        </View>
      ) : null}

      <View style={styles.searchBox}>
        <Icon name="magnify" size={20} color={colors.textTertiary} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          style={styles.searchInput}
          placeholder="搜索工人姓名、电话或默认工价"
          placeholderTextColor={colors.textTertiary}
        />
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>工人列表</Text>
        <Text style={styles.sectionMeta}>{filteredWorkers.length} 人</Text>
      </View>

      {filteredWorkers.length === 0 ? (
        <EmptyState
          title="暂无工人"
          subtitle="保存工资时会自动创建轻档案"
          actionLabel="去记工资"
          onAction={() => navigation.navigate("WageCreate", {})}
          icon="account-hard-hat-outline"
        />
      ) : (
        <View style={styles.list}>
          {filteredWorkers.map((worker) => {
            const unpaid = toNumber(worker.total_unpaid);
            const recent = worker.cycle_summaries
              .map((cycle) => cycle.cycle_name)
              .filter(Boolean)
              .slice(0, 2)
              .join("、");
            return (
              <TouchableOpacity
                key={worker.id}
                style={styles.workerRow}
                activeOpacity={0.75}
                onPress={() =>
                  navigation.navigate("WageCreate", {
                    workerName: worker.name,
                  })
                }
              >
                <View style={styles.avatar}>
                  <Text style={styles.avatarText}>{getInitial(worker.name)}</Text>
                </View>
                <View style={styles.workerInfo}>
                  <Text style={styles.workerName}>{worker.name}</Text>
                  <Text style={styles.workerMeta} numberOfLines={1}>
                    {recent || "暂未关联茬口"}
                    {worker.default_unit_price ? ` · 常用 ${worker.default_unit_price}/天` : ""}
                  </Text>
                </View>
                <View style={styles.workerMoney}>
                  <Text style={[styles.unpaidText, unpaid > 0 ? styles.moneyDanger : styles.moneyOk]}>
                    {unpaid > 0 ? `欠 ${formatMoney(unpaid)}` : "结清"}
                  </Text>
                  <Text style={styles.entryText}>{worker.entry_count} 笔</Text>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      )}

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>最近参与茬口</Text>
        <TouchableOpacity onPress={openLedger}>
          <Text style={styles.sectionLink}>到账单页</Text>
        </TouchableOpacity>
      </View>

      {recentCycles.length > 0 ? (
        <View style={styles.list}>
          {recentCycles.map((cycle) => (
            <TouchableOpacity
              key={`${cycle.workerName}-${cycle.cycle_id}-${cycle.recent_work_date || ""}`}
              style={styles.cycleRow}
              onPress={() =>
                navigation.navigate("CostList", {
                  filters: {
                    cycleId: cycle.cycle_id,
                    category: "人工",
                    sourceType: "labor_entry",
                    title: `${cycle.cycle_name}人工账单`,
                  },
                })
              }
            >
              <Icon name="sprout-outline" size={20} color={colors.success} />
              <View style={styles.cycleInfo}>
                <Text style={styles.cycleName}>{cycle.cycle_name}</Text>
                <Text style={styles.workerMeta}>
                  {cycle.workerName} · {cycle.recent_operation_type || "用工"} · 欠 {formatMoney(cycle.total_unpaid)}
                </Text>
              </View>
              <Icon name="chevron-right" size={20} color={colors.textTertiary} />
            </TouchableOpacity>
          ))}
        </View>
      ) : (
        <Text style={styles.emptyText}>记工资后会在这里看到跨茬口参与记录。</Text>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacingV2.lg, paddingBottom: spacingV2.xxxxl },
  hero: {
    backgroundColor: colors.headerBg,
    borderRadius: borderRadiusV2.xxxl,
    padding: spacingV2.xl,
    marginBottom: spacingV2.lg,
  },
  heroTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  heroLabel: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255,255,255,0.72)",
    fontWeight: "700",
  },
  heroValue: {
    marginTop: spacingV2.xs,
    fontSize: fontSizeV2.xxxl,
    color: colors.textInverse,
    fontWeight: "800",
  },
  heroIcon: {
    width: 44,
    height: 44,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.14)",
  },
  metricRow: { flexDirection: "row", gap: spacingV2.sm },
  metricItem: {
    flex: 1,
    padding: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: "rgba(255,255,255,0.10)",
  },
  metricValue: {
    fontSize: fontSizeV2.lg,
    color: colors.textInverse,
    fontWeight: "800",
  },
  metricLabel: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: "rgba(255,255,255,0.66)",
    fontWeight: "600",
  },
  actionRow: { flexDirection: "row", gap: spacingV2.md, marginBottom: spacingV2.md },
  actionButton: { flex: 1, minHeight: 48 },
  outlineButton: {
    minHeight: 48,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacingV2.xs,
  },
  outlineText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "700",
  },
  notice: {
    flexDirection: "row",
    gap: spacingV2.xs,
    padding: spacingV2.md,
    borderRadius: borderRadiusV2.lg,
    backgroundColor: colors.infoLight,
    marginBottom: spacingV2.md,
  },
  noticeText: { flex: 1, fontSize: fontSizeV2.sm, color: colors.info, lineHeight: 19 },
  searchBox: {
    minHeight: 44,
    borderRadius: borderRadiusV2.xl,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.surface,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    paddingHorizontal: spacingV2.md,
  },
  searchInput: { flex: 1, minWidth: 0, fontSize: fontSizeV2.md, color: colors.text },
  sectionHeader: {
    marginTop: spacingV2.xl,
    marginBottom: spacingV2.md,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  sectionTitle: { fontSize: fontSizeV2.lg, fontWeight: "800", color: colors.text },
  sectionMeta: { fontSize: fontSizeV2.sm, color: colors.textSecondary, fontWeight: "600" },
  sectionLink: { fontSize: fontSizeV2.sm, color: colors.primary, fontWeight: "800" },
  list: {
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  workerRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacingV2.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
    gap: spacingV2.md,
  },
  avatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.successMuted,
  },
  avatarText: { color: colors.success, fontWeight: "900", fontSize: fontSizeV2.md },
  workerInfo: { flex: 1, minWidth: 0 },
  workerName: { fontSize: fontSizeV2.md, fontWeight: "800", color: colors.text },
  workerMeta: {
    marginTop: 3,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  workerMoney: { alignItems: "flex-end", minWidth: 62 },
  unpaidText: { fontSize: fontSizeV2.sm, fontWeight: "900" },
  moneyDanger: { color: colors.danger },
  moneyOk: { color: colors.success },
  entryText: { marginTop: 2, fontSize: fontSizeV2.xs, color: colors.textTertiary },
  cycleRow: {
    flexDirection: "row",
    alignItems: "center",
    padding: spacingV2.lg,
    gap: spacingV2.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  cycleInfo: { flex: 1, minWidth: 0 },
  cycleName: { fontSize: fontSizeV2.md, fontWeight: "800", color: colors.text },
  emptyText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    lineHeight: 22,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
  },
});
