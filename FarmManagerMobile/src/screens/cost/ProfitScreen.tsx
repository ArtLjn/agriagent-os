import React, { useEffect } from "react";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import { useRoute } from "@react-navigation/native";
import { useCostStore } from "../../stores/costStore";
import { Card } from "../../components/Card";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacing, fontSize } from "../../theme/spacing";

type ProfitRouteProp = {
  params: { cycleId: number };
};

export const ProfitScreen: React.FC = () => {
  const route = useRoute() as ProfitRouteProp;
  const { cycleId } = route.params;
  const { profit, loading, fetchProfit } = useCostStore();

  useEffect(() => {
    fetchProfit(cycleId);
  }, [cycleId, fetchProfit]);

  if (loading) {
    return <Loading message="加载利润统计中..." />;
  }

  const net = profit ? parseFloat(profit.net_profit) : 0;
  const isProfit = net >= 0;

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
});
