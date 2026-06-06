import React, { useMemo, useState, useCallback } from "react";
import { showAlert } from "../../utils/alert";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import {
  useFocusEffect,
  useNavigation,
  useRoute,
  type RouteProp,
} from "@react-navigation/native";
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
import { LedgerHeroHeader } from "./components/LedgerHeroHeader";
import { LedgerFilters } from "./components/LedgerFilters";
import { LedgerSearchBox } from "./components/LedgerSearchBox";
import { LedgerSourceBanner } from "./components/LedgerSourceBanner";
import { LedgerSummaryCard } from "./components/LedgerSummaryCard";
import { RecordItem } from "./components/RecordItem";
import { RecordDetailModal } from "./components/RecordDetailModal";
import {
  filterCostRecords,
  formatRecordAmount,
  type DateRangeFilter,
  type RecordFilterType,
} from "./utils/recordDisplay";

type FilterType = RecordFilterType;

type CostListNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  "CostList"
>;
type CostListRouteProp = RouteProp<RootStackParamList, "CostList">;

interface DayGroup {
  date: string;
  title: string;
  records: CostRecord[];
  dayCost: number;
  dayIncome: number;
}

function formatSectionTitle(dateStr: string): string {
  const d = dayjs(dateStr);
  const today = dayjs();
  if (d.isSame(today, "day")) {
    return "今天";
  }
  if (d.isSame(today.subtract(1, "day"), "day")) {
    return "昨天";
  }
  if (d.year() === today.year()) {
    return d.format("M月D日");
  }
  return d.format("YYYY年M月D日");
}

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const route = useRoute<CostListRouteProp>();
  const { records, loading, fetchRecords, deleteRecord } = useCostStore();
  const routeFilters = route.params?.filters;
  const routeCategory = routeFilters?.category;
  const routeCycleId = routeFilters?.cycleId;
  const routeSourceId = routeFilters?.sourceId;
  const routeSourceType = routeFilters?.sourceType;
  const [filter, setFilter] = useState<FilterType>("all");
  const [dateRange, setDateRange] = useState<DateRangeFilter>(
    routeFilters ? "all" : "month"
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CostRecord | null>(null);

  useFocusEffect(
    useCallback(() => {
      fetchRecords(
        routeFilters
          ? {
              cycle_id: routeCycleId,
              category: routeCategory,
              source_type: routeSourceType,
              source_id: routeSourceId,
            }
          : undefined
      );
    }, [
      fetchRecords,
      routeCategory,
      routeCycleId,
      routeFilters,
      routeSourceId,
      routeSourceType,
    ])
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
    return { cost, income, balance: income - cost, count: monthRecords.length };
  }, [records, currentMonth]);

  const categoryList = useMemo(() => {
    const categories = new Set(records.map((r) => r.category));
    return Array.from(categories);
  }, [records]);

  const filteredRecords = useMemo(
    () =>
      filterCostRecords(records, {
        query: searchQuery,
        type: filter,
        dateRange,
        month: currentMonth,
        category: categoryFilter ?? routeCategory,
        cycleId: routeCycleId,
        sourceType: routeSourceType,
        sourceId: routeSourceId,
      }),
    [
      records,
      searchQuery,
      filter,
      dateRange,
      currentMonth,
      categoryFilter,
      routeCategory,
      routeCycleId,
      routeSourceId,
      routeSourceType,
    ]
  );

  const resultStats = useMemo(() => {
    const cost = filteredRecords
      .filter((r) => r.record_type === "cost")
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    const income = filteredRecords
      .filter((r) => r.record_type === "income")
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    return { cost, income, count: filteredRecords.length };
  }, [filteredRecords]);

  const dayGroups = useMemo<DayGroup[]>(() => {
    const groups: Record<string, CostRecord[]> = {};
    for (const r of filteredRecords) {
      if (!groups[r.record_date]) {
        groups[r.record_date] = [];
      }
      groups[r.record_date].push(r);
    }

    return Object.entries(groups)
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, data]) => ({
        date,
        title: formatSectionTitle(date),
        records: data.sort((a, b) => {
          const aTime = a.created_at ? dayjs(a.created_at).valueOf() : 0;
          const bTime = b.created_at ? dayjs(b.created_at).valueOf() : 0;
          return bTime - aTime || b.id - a.id;
        }),
        dayCost: data
          .filter((r) => r.record_type === "cost")
          .reduce((s, r) => s + parseFloat(r.amount), 0),
        dayIncome: data
          .filter((r) => r.record_type === "income")
          .reduce((s, r) => s + parseFloat(r.amount), 0),
      }));
  }, [filteredRecords]);

  const handleCreate = () => {
    navigation.navigate("CostCreate");
  };

  const handleFilterChange = (newFilter: FilterType) => {
    setFilter(newFilter);
    setCategoryFilter(null);
  };

  const handleDateRangeChange = (newRange: DateRangeFilter) => {
    setDateRange(newRange);
    if (newRange === "today" || newRange === "week") {
      setSelectedMonth(new Date());
    }
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
          } catch {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  const handleOpenSource = (record: CostRecord) => {
    setDetailVisible(false);
    if (record.source_type === "labor_entry") {
      navigation.navigate("WorkerList");
      return;
    }
    if (record.source_type === "operation_work_order") {
      if (record.cycle_id) {
        navigation.navigate("CostList", {
          filters: {
            cycleId: record.cycle_id,
            category: "人工",
            sourceType: "operation_work_order",
            sourceId: record.source_id || undefined,
            title: "农事作业人工账单",
          },
        });
      }
      return;
    }
    if (record.cycle_id) {
      navigation.navigate("CostList", {
        filters: {
          cycleId: record.cycle_id,
          sourceType: record.source_type || undefined,
          sourceId: record.source_id || undefined,
          title: "来源账单",
        },
      });
    }
  };

  const renderDayCard = ({ item }: { item: DayGroup }) => (
    <View style={styles.dayCard}>
      <View style={styles.dayHeader}>
        <Text style={styles.dayTitle}>{item.title}</Text>
        <View style={styles.daySummary}>
          {item.dayIncome > 0 && (
            <Text style={styles.dayIncomeBadge}>
              +{formatRecordAmount(String(item.dayIncome))}
            </Text>
          )}
          {item.dayCost > 0 && (
            <Text style={styles.dayCostBadge}>
              -{formatRecordAmount(String(item.dayCost))}
            </Text>
          )}
        </View>
      </View>
      {item.records.map((record, index) => (
        <React.Fragment key={record.id}>
          {index > 0 && <View style={styles.divider} />}
          <RecordItem
            item={record}
            onPress={() => handleShowDetail(record)}
            onLongPress={() => handleDelete(record)}
          />
        </React.Fragment>
      ))}
    </View>
  );

  const ListFooter = <View style={{ height: 90 }} />;

  const ListHeader = (
    <>
      <LedgerHeroHeader
        selectedMonth={selectedMonth}
        onPreviousMonth={handlePreviousMonth}
        onNextMonth={handleNextMonth}
      />
      <LedgerSummaryCard
        income={stats.income}
        cost={stats.cost}
        count={stats.count}
      />

      {routeFilters ? (
        <LedgerSourceBanner
          title={routeFilters.title}
          cycleId={routeFilters.cycleId}
          category={routeFilters.category}
          sourceType={routeFilters.sourceType}
        />
      ) : null}

      <LedgerSearchBox value={searchQuery} onChange={setSearchQuery} />

      <Text style={styles.resultSummary}>
        {searchQuery || filter !== "all" || dateRange !== "month" || categoryFilter
          ? `找到 ${resultStats.count} 条 · 收入 +${formatRecordAmount(String(resultStats.income))} · 支出 -${formatRecordAmount(String(resultStats.cost))}`
          : `共 ${resultStats.count} 条记录 · 本月`}
      </Text>

      <LedgerFilters
        filter={filter}
        dateRange={dateRange}
        categoryList={categoryList}
        categoryFilter={categoryFilter}
        onFilterChange={handleFilterChange}
        onDateRangeChange={handleDateRangeChange}
        onCategoryFilterChange={setCategoryFilter}
      />
    </>
  );

  if (loading && records.length === 0) {
    return <Loading message="加载账单中..." />;
  }

  if (records.length === 0) {
    return (
      <View style={styles.container}>
        <LedgerHeroHeader
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
      <FlatList
        data={dayGroups}
        keyExtractor={(item) => item.date}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={ListHeader}
        renderItem={renderDayCard}
        ListFooterComponent={ListFooter}
        ListEmptyComponent={
          <View style={styles.emptyWrap}>
            <View style={styles.emptyContainer}>
              <Icon
                name="clipboard-text-outline"
                size={48}
                color={colors.textTertiary}
              />
              <Text style={styles.emptyText}>没有找到记录</Text>
              <Text style={styles.emptySubtext}>
                试试搜索关键词或切换筛选条件
              </Text>
            </View>
          </View>
        }
      />

      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Icon name="plus" size={20} color={colors.textInverse} />
        <Text style={styles.fabText}>记一笔</Text>
      </TouchableOpacity>

      <RecordDetailModal
        visible={detailVisible}
        record={selectedRecord}
        onClose={() => setDetailVisible(false)}
        onOpenSource={handleOpenSource}
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
  resultSummary: {
    marginHorizontal: spacingV2.lg,
    marginTop: -spacingV2.xs,
    marginBottom: spacingV2.sm,
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  dayCard: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    borderRadius: borderRadiusV2.xxxl,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 3,
    overflow: "hidden",
  },
  dayHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.md,
    paddingBottom: spacingV2.sm,
  },
  dayTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    color: colors.textSecondary,
    letterSpacing: -0.2,
  },
  daySummary: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  dayIncomeBadge: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.income,
  },
  dayCostBadge: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.expense,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0,0,0,0.04)",
    marginHorizontal: spacingV2.lg,
  },
  emptyWrap: {
    flex: 1,
    minHeight: 400,
    alignItems: "center",
    justifyContent: "center",
  },
  emptyContainer: {
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: spacingV2.xxxl,
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
    height: 52,
    paddingHorizontal: spacingV2.lg,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.primary,
    flexDirection: "row",
    gap: spacingV2.xs,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.2,
    shadowRadius: 14,
    elevation: 5,
  },
  fabText: {
    fontSize: fontSizeV2.md,
    color: colors.textInverse,
    fontWeight: "700",
  },
});
