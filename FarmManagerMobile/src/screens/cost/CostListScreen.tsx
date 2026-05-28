import React, { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
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

const AssetCard: React.FC<{ income: number; cost: number }> = ({
  income,
  cost,
}) => {
  const total = income - cost;
  const isPositive = total >= 0;
  return (
    <View style={assetStyles.card}>
      <View style={assetStyles.mainSection}>
        <Text style={assetStyles.label}>本月结余</Text>
        <Text
          style={[
            assetStyles.total,
            { color: isPositive ? colors.income : colors.expense },
          ]}
        >
          {isPositive ? "+" : ""}
          {total.toFixed(2)}
        </Text>
      </View>
      <View style={assetStyles.divider} />
      <View style={assetStyles.subRow}>
        <View style={assetStyles.subItem}>
          <View style={assetStyles.subItemInner}>
            <View
              style={[
                assetStyles.dot,
                { backgroundColor: colors.income },
              ]}
            />
            <Text style={assetStyles.subLabel}>收入</Text>
          </View>
          <Text style={[assetStyles.subAmount, { color: colors.income }]}>
            +{income.toFixed(2)}
          </Text>
        </View>
        <View style={assetStyles.subDivider} />
        <View style={assetStyles.subItem}>
          <View style={assetStyles.subItemInner}>
            <View
              style={[
                assetStyles.dot,
                { backgroundColor: colors.expense },
              ]}
            />
            <Text style={assetStyles.subLabel}>支出</Text>
          </View>
          <Text style={[assetStyles.subAmount, { color: colors.expense }]}>
            -{cost.toFixed(2)}
          </Text>
        </View>
      </View>
    </View>
  );
};

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const { records, loading, fetchRecords, deleteRecord } = useCostStore();
  const [filter, setFilter] = useState<FilterType>("all");
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CostRecord | null>(null);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

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


  const filteredRecords = useMemo(() => {
    let result = records.filter((r) => r.record_date.startsWith(currentMonth));
    if (filter !== "all") {
      result = result.filter((r) => r.record_type === filter);
    }
    if (categoryFilter) {
      result = result.filter((r) => r.category === categoryFilter);
    }
    return result;
  }, [records, currentMonth, filter, categoryFilter]);

  const handleCreate = () => {
    navigation.navigate("CostCreate");
  };

  const handlePreviousMonth = () => {
    setSelectedMonth(dayjs(selectedMonth).subtract(1, "month").toDate());
  };

  const handleNextMonth = () => {
    const nextMonth = dayjs(selectedMonth).add(1, "month");
    const now = dayjs();
    // 不允许选择未来月份
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
    Alert.alert("确认删除", "确定要删除这条记录吗？", [
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
      {/* Month Selector */}
      <MonthlyStats
        selectedMonth={selectedMonth}
        onPreviousMonth={handlePreviousMonth}
        onNextMonth={handleNextMonth}
      />

      {/* Asset Summary */}
      <AssetCard income={stats.income} cost={stats.cost} />

      {/* Filters: Type + Category in one row */}
      <View style={styles.filterSection}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterScrollContent}
        >
          {/* Type filters */}
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
                onPress={() => setFilter(item.key)}
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

          {/* Divider */}
          {categoryList.length > 0 && (
            <View style={styles.filterDivider} />
          )}

          {/* Category filters */}
          {categoryList.map((cat) => {
            const isActive = categoryFilter === cat;
            return (
              <TouchableOpacity
                key={`cat-${cat}`}
                style={[
                  styles.filterChip,
                  isActive && styles.filterChipActive,
                ]}
                onPress={() =>
                  setCategoryFilter(isActive ? null : cat)
                }
                activeOpacity={0.7}
              >
                <Text
                  style={[
                    styles.filterChipText,
                    isActive && styles.filterChipTextActive,
                  ]}
                >
                  {cat}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>

      {/* List */}
      <FlatList
        data={filteredRecords}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={[
          styles.listContent,
          filteredRecords.length === 0 && styles.listEmpty,
        ]}
        showsVerticalScrollIndicator={false}
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
        renderItem={({ item }) => (
          <RecordItem
            item={item}
            onPress={() => handleShowDetail(item)}
            onLongPress={() => handleDelete(item)}
          />
        )}
      />
      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Icon name="plus" size={24} color={colors.textInverse} />
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
    backgroundColor: colors.surfaceMuted,
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
    fontWeight: "600",
  },
  filterDivider: {
    width: 1,
    height: 20,
    backgroundColor: colors.border,
    marginHorizontal: spacingV2.xs,
  },
  listContent: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.xxxl,
  },
  listEmpty: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyContainer: {
    alignItems: "center",
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
    width: 52,
    height: 52,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#5B8CFF",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
    elevation: 6,
  },
});

const assetStyles = StyleSheet.create({
  card: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 3,
    overflow: "hidden",
  },
  mainSection: {
    padding: spacingV2.lg,
    paddingBottom: spacingV2.md,
    alignItems: "center",
  },
  label: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "500",
    marginBottom: spacingV2.xs,
  },
  total: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "700",
    letterSpacing: -1,
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0,0,0,0.04)",
    marginHorizontal: spacingV2.lg,
  },
  subRow: {
    flexDirection: "row",
    paddingVertical: spacingV2.md,
    paddingHorizontal: spacingV2.lg,
  },
  subItem: {
    flex: 1,
    alignItems: "center",
  },
  subItemInner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    marginBottom: 2,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  subDivider: {
    width: 1,
    backgroundColor: "rgba(0,0,0,0.06)",
  },
  subLabel: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  subAmount: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    letterSpacing: -0.2,
  },
});
