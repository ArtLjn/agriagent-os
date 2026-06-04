import React, { useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import { useNavigation, useRoute } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { costApi } from "../../api/client";
import { useCostStore } from "../../stores/costStore";
import { Card } from "../../components/Card";
import { Loading } from "../../components/Loading";
import type { RootStackParamList } from "../../navigation/AppNavigator";
import { colors } from "../../theme/colors";
import { spacing, fontSize } from "../../theme/spacing";

type ProfitRouteProp = {
  params: { cycleId: number };
};
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const ProfitScreen: React.FC = () => {
  const route = useRoute() as ProfitRouteProp;
  const navigation = useNavigation<NavigationProp>();
  const { cycleId } = route.params;
  const { profit, loading, fetchProfit } = useCostStore();
  const [ledgerLaborCost, setLedgerLaborCost] = useState({
    total: "0.00",
    laborEntry: "0.00",
    operationLabor: "0.00",
  });

  useEffect(() => {
    fetchProfit(cycleId);
    costApi
      .getRecords({
        cycle_id: cycleId,
        category: "人工",
      })
      .then((res) => {
        const items = (res.data as any)?.items ?? res.data ?? [];
        const sumBySource = (sourceType?: string) =>
          items
            .filter((item: { source_type?: string | null }) =>
              sourceType ? item.source_type === sourceType : true
            )
            .reduce(
              (sum: number, item: { amount?: string }) =>
                sum + Number(item.amount || 0),
              0
            );
        setLedgerLaborCost({
          total: sumBySource().toFixed(2),
          laborEntry: sumBySource("labor_entry").toFixed(2),
          operationLabor: sumBySource("operation_work_order").toFixed(2),
        });
      })
      .catch(() =>
        setLedgerLaborCost({
          total: "0.00",
          laborEntry: "0.00",
          operationLabor: "0.00",
        })
      );
  }, [cycleId, fetchProfit]);

  const openLaborLedger = (sourceType?: string) => {
    navigation.navigate("CostList", {
      filters: {
        cycleId,
        category: "人工",
        sourceType,
        title:
          sourceType === "labor_entry"
            ? "人工工资账单"
            : sourceType === "operation_work_order"
              ? "农事作业人工账单"
              : "全部人工账单",
      },
    });
  };

  const getAmount = (value?: string) => value || "0.00";

  const net = profit ? parseFloat(profit.net_profit) : 0;
  const isProfit = net >= 0;
  const laborCost = getAmount(profit?.labor_cost || ledgerLaborCost.total);
  const laborEntryCost = getAmount(
    profit?.labor_entry_cost || ledgerLaborCost.laborEntry
  );
  const operationLaborCost = getAmount(
    profit?.operation_labor_cost || ledgerLaborCost.operationLabor
  );

  if (loading) {
    return <Loading message="加载利润统计中..." />;
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerLabel}>净利润</Text>
        <Text
          style={[
            styles.netProfit,
            { color: isProfit ? colors.success : colors.danger },
          ]}
        >
          {isProfit ? "+" : ""}
          {profit?.net_profit ?? "0.00"}
        </Text>
        <Text style={styles.headerUnit}>元</Text>
      </View>

      <View style={styles.cardsRow}>
        <View style={styles.summaryCard}>
          <Card style={styles.costCard} padding="lg">
            <Text style={styles.cardLabel}>总支出</Text>
            <Text style={[styles.cardValue, { color: colors.danger }]}>
              -{profit?.total_cost ?? "0.00"}
            </Text>
          </Card>
        </View>
        <View style={styles.summaryCard}>
          <Card style={styles.incomeCard} padding="lg">
            <Text style={styles.cardLabel}>总收入</Text>
            <Text style={[styles.cardValue, { color: colors.success }]}>
              +{profit?.total_income ?? "0.00"}
            </Text>
          </Card>
        </View>
      </View>

      <TouchableOpacity
        style={styles.laborCard}
        activeOpacity={0.75}
        onPress={() => openLaborLedger()}
      >
        <View>
          <Text style={styles.cardLabel}>人工成本</Text>
          <Text style={[styles.cardValue, { color: colors.danger }]}>
            -{laborCost}
          </Text>
        </View>
        <Text style={styles.linkText}>查看明细</Text>
      </TouchableOpacity>

      <View style={styles.laborBreakdown}>
        <TouchableOpacity
          style={styles.breakdownItem}
          activeOpacity={0.75}
          onPress={() => openLaborLedger("labor_entry")}
        >
          <Text style={styles.breakdownLabel}>工资记录</Text>
          <Text style={styles.breakdownValue}>-{laborEntryCost}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.breakdownItem}
          activeOpacity={0.75}
          onPress={() => openLaborLedger("operation_work_order")}
        >
          <Text style={styles.breakdownLabel}>农事作业</Text>
          <Text style={styles.breakdownValue}>-{operationLaborCost}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerLabel: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  netProfit: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
  },
  headerUnit: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  cardsRow: {
    flexDirection: "row",
    padding: spacing.md,
    gap: spacing.md,
  },
  summaryCard: {
    flex: 1,
  },
  costCard: {
    borderLeftWidth: 4,
    borderLeftColor: colors.danger,
    alignItems: "center",
  },
  incomeCard: {
    borderLeftWidth: 4,
    borderLeftColor: colors.success,
    alignItems: "center",
  },
  cardLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  cardValue: {
    fontSize: fontSize.xl,
    fontWeight: "700",
  },
  laborCard: {
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    padding: spacing.lg,
    borderRadius: 18,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  linkText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: "700",
  },
  laborBreakdown: {
    flexDirection: "row",
    gap: spacing.md,
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
  },
  breakdownItem: {
    flex: 1,
    padding: spacing.md,
    borderRadius: 16,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  breakdownLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  breakdownValue: {
    fontSize: fontSize.lg,
    color: colors.danger,
    fontWeight: "700",
  },
});
