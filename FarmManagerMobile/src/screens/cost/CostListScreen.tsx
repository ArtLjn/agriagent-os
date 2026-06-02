import React, { useMemo, useState, useCallback } from "react";
import { showAlert } from "../../utils/alert";
import {
  View,
  Text,
  SectionList,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
 
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import dayjs from "dayjs";
import { useCostStore } from "../../stores/costStore";
import type { CostRecord } from "../../api/types";
import { EmptyState } from "../../components/EmptyState";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { MonthlyStats } from "./components/MonthlyStats";
import { RecordItem } from "./components/RecordItem";
import { RecordDetailModal } from "./components/RecordDetailModal";

type FilterType = "all" | "cost" | "income";

type CostListNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "CostCreate"
>;

interface Section {
  title: string;
  data: CostRecord[];
  dayCost: number;
  dayIncome: number;
}

const AssetCard: React.FC<{ income: number; cost: number }> = ({
  income,
  cost,
}) => {
  const total = income - cost;
  const isPositive = total >= 0;
  const accentColor = isPositive ? colors.income : colors.expense;
  const bgColor = isPositive ? colors.incomeBg : colors.expenseBg;

  return (
    <View style={[assetStyles.card, { backgroundColor: bgColor }]}>
      <View style={assetStyles.mainSection}>
        <Text style={assetStyles.label}>本月结余</Text>
        <Text style={[assetStyles.total, { color: accentColor }]}>
          {isPositive ? "+" : ""}
          {total.toFixed(2)}
        </Text>
      </View>
      <View style={assetStyles.subRow}>
        <View style={assetStyles.subItem}>
          <Text style={assetStyles.subLabel}>收入</Text>
          <Text style={[assetStyles.subAmount, { color: colors.income }]}>
            +{income.toFixed(2)}
          </Text>
        </View>
        <View style={assetStyles.subDivider} />
        <View style={assetStyles.subItem}>
          <Text style={assetStyles.subLabel}>支出</Text>
          <Text style={[assetStyles.subAmount, { color: colors.expense }]}>
            -{cost.toFixed(2)}
          </Text>
        </View>
      </View>
    </View>
  );
};

function formatSectionTitle(dateStr: string): string {
  const d = dayjs(dateStr);
  const today = dayjs();
  if (d.isSame(today, "day")) return "今天";
  if (d.isSame(today.subtract(1, "day"), "day")) return "昨天";
  if (d.year() === today.year()) return d.format("M月D日");
  return d.format("YYYY年M月D日");
}

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const { records, loading, fetchRecords, deleteRecord } = useCostStore();
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CostRecord | null>(null);

  useFocusEffect(
    useCallback(() => {
      fetchRecords();
    }, [fetchRecords])
  );

  const currentMonth = dayjs(selectedMonth).format("YYYY-MM");

  const stats = useMemo(() => {
    const monthRecords = records.filter((r) =>
      r.record_date.startsWith(currentMonth)
    );
    const cost = monthRecords
      .filter((r) => r.record_type === "cost")
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    const income = monthRecords
      .filter((r) => r.record_type === "income")
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    return { cost, income, balance: income - cost };
  }, [records, currentMonth]);

  const categoryList = useMemo(() => {
    const categories = new Set(records.map((r) => r.category));
    return Array.from(categories);
  }, [records]);

  const sections = useMemo<Section[]>(() => {
    let result = records.filter((r) => r.record_date.startsWith(currentMonth));
    if (filter !== "all") {
      result = result.filter((r) => r.record_type === filter);
    }
    if (categoryFilter) {
      result = result.filter((r) => r.category === categoryFilter);
    }

    const groups: Record<string, CostRecord[]> = {};
    for (const r of result) {
      if (!groups[r.record_date]) groups[r.record_date] = [];
      groups[r.record_date].push(r);
    }

    return Object.entries(groups)
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, data]) => ({
        title: formatSectionTitle(date),
        data,
        dayCost: data
          .filter((r) => r.record_type === "cost")
          .reduce((s, r) => s + parseFloat(r.amount), 0),
        dayIncome: data
          .filter((r) => r.record_type === "income")
          .reduce((s, r) => s + parseFloat(r.amount), 0),
      }));
  }, [records, currentMonth, filter, categoryFilter]);

  const handleCreate = () => {
    navigation.navigate("CostCreate");
  };

  const handleFilterChange = (newFilter: FilterType) => {
    setFilter(newFilter);
    setCategoryFilter(null);
  };

  const handlePreviousMonth = () => {
    setSelectedMonth(dayjs(selectedMonth).subtract(1, "month").toDate());
  };

  const handleNextMonth = () => {
    const nextMonth = dayjs(selectedMonth).add(1, "month");
    const now = dayjs();
    const nextYM = nextMonth.year() * 12 + nextMonth.month();
    const nowYM = now.year() * 12 + now.month();
    if (nextYM <= nowYM) {
      setSelectedMonth(nextMonth.toDate());
    }
  };

  const handleShowDetail = (record: CostRecord) => {
    setSelectedRecord(record);
    setDetailVisible(true);
  };

  const handleDelete = (record: CostRecord) => {
    showAlert("确认删除", "确定要删除这条记录吗？", [
      { text: "取消", style: "cancel" },
      {
        text: "删除",
        style: "destructive",
        onPress: async () => {
          try {
            await deleteRecord(record.id, record.cycle_id || undefined);
          } catch (err) {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  if (loading && records.length === 0) {
    return <Loading message="加载账单中..." />;
  }

  if (records.length === 0) {
    return (
      <View style={styles.container}>
        <MonthlyStats
          selectedMonth={selectedMonth}
          onPreviousMonth={handlePreviousMonth}
          onNextMonth={handleNextMonth}
        />
        <EmptyState
          title="暂无账单记录"
          subtitle="点击按钮记一笔"
          actionLabel="记一笔"
          onAction={handleCreate}
          icon="cash-remove"
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <SectionList
        sections={sections}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <>
            <MonthlyStats
              selectedMonth={selectedMonth}
              onPreviousMonth={handlePreviousMonth}
              onNextMonth={handleNextMonth}
            />
            <AssetCard income={stats.income} cost={stats.cost} />

            {/* Filters */}
            <View style={styles.filterSection}>
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.filterScrollContent}
              >
                {(
                  [
                    { key: "all", label: "全部" },
                    { key: "cost", label: "支出" },
                    { key: "income", label: "收入" },
                  ] as { key: FilterType; label: string }[]
                ).map((item) => {
                  const isActive = filter === item.key;
                  return (
                    <TouchableOpacity
                      key={`type-${item.key}`}
                      style={[
                        styles.filterChip,
                        isActive && styles.filterChipActive,
                      ]}
                      onPress={() => handleFilterChange(item.key)}
                      activeOpacity={0.7}
                    >
                      <Text
                        style={[
                          styles.filterChipText,
                          isActive && styles.filterChipTextActive,
                        ]}
                      >
                        {item.label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </ScrollView>

              {categoryList.length > 0 && (
                <ScrollView
                  horizontal
                  showsHorizontalScrollIndicator={false}
                  contentContainerStyle={styles.filterCatScrollContent}
                >
                  {categoryList.map((cat) => {
                    const isActive = categoryFilter === cat;
                    return (
                      <TouchableOpacity
                        key={`cat-${cat}`}
                        style={[
                          styles.filterCatChip,
                          isActive && styles.filterCatChipActive,
                        ]}
                        onPress={() =>
                          setCategoryFilter(isActive ? null : cat)
                        }
                        activeOpacity={0.7}
                      >
                        <Text
                          style={[
                            styles.filterCatChipText,
                            isActive && styles.filterCatChipTextActive,
                          ]}
                        >
                          {cat}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              )}
            </View>
          </>
        }
        renderSectionHeader={({ section }) => (
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>{section.title}</Text>
            <View style={styles.sectionSummary}>
              {section.dayIncome > 0 && (
                <Text style={styles.sectionIncome}>
                  +{section.dayIncome.toFixed(0)}
                </Text>
              )}
              {section.dayCost > 0 && (
                <Text style={styles.sectionCost}>
                  -{section.dayCost.toFixed(0)}
                </Text>
              )}
            </View>
          </View>
        )}
        renderItem={({ item }) => (
          <RecordItem
            item={item}
            onPress={() => handleShowDetail(item)}
            onLongPress={() => handleDelete(item)}
          />
        )}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon
              name="clipboard-text-outline"
              size={48}
              color={colors.textTertiary}
            />
            <Text style={styles.emptyText}>本月暂无记录</Text>
            <Text style={styles.emptySubtext}>点击右下角按钮记一笔</Text>
          </View>
        }
      />

      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Icon name="plus" size={22} color={colors.textInverse} />
      </TouchableOpacity>

      <RecordDetailModal
        visible={detailVisible}
        record={selectedRecord}
        onClose={() => setDetailVisible(false)}
        onDelete={() => {
          setDetailVisible(false);
          if (selectedRecord) {
            handleDelete(selectedRecord);
          }
        }}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    paddingBottom: 100,
  },
  filterSection: {
    marginBottom: spacingV2.sm,
  },
  filterScrollContent: {
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.xs,
    gap: spacingV2.xs,
    alignItems: "center",
  },
  filterChip: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: 6,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surface,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 2,
    elevation: 1,
  },
  filterChipActive: {
    backgroundColor: colors.primaryMuted,
  },
  filterChipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  filterChipTextActive: {
    color: colors.primary,
    fontWeight: "700",
  },
  filterCatScrollContent: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.xs,
    gap: spacingV2.xs,
    alignItems: "center",
  },
  filterCatChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  filterCatChipActive: {
    backgroundColor: colors.primaryMuted,
  },
  filterCatChipText: {
    fontSize: 12,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  filterCatChipTextActive: {
    color: colors.primary,
    fontWeight: "600",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.sm,
  },
  sectionTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
  },
  sectionSummary: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  sectionIncome: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.income,
  },
  sectionCost: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.expense,
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacingV2.xxxl,
    minHeight: 280,
  },
  emptyText: {
    fontSize: fontSizeV2.lg,
    color: colors.textSecondary,
    fontWeight: "600",
    marginTop: spacingV2.lg,
  },
  emptySubtext: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: spacingV2.xs,
  },
  fab: {
    position: "absolute",
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    width: 52,
    height: 52,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 5,
  },
});

const assetStyles = StyleSheet.create({
  card: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    borderRadius: borderRadiusV2.xxxl,
    overflow: "hidden",
  },
  mainSection: {
    padding: spacingV2.xl,
    paddingBottom: spacingV2.lg,
    alignItems: "center",
  },
  label: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    marginBottom: spacingV2.xs,
  },
  total: {
    fontSize: fontSizeV2.xxxxl,
    fontWeight: "800",
    letterSpacing: -1.5,
  },
  subRow: {
    flexDirection: "row",
    paddingVertical: spacingV2.md,
    paddingHorizontal: spacingV2.lg,
    borderTopWidth: 1,
    borderTopColor: "rgba(0,0,0,0.06)",
  },
  subItem: {
    flex: 1,
    alignItems: "center",
    gap: 2,
  },
  subDivider: {
    width: 1,
  },
  subLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  subAmount: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
});
