import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { formatCompactNumber } from "../../utils/numberFormat";
import type { ReportCostItem } from "../../api/types";

interface CostBreakdownCardProps {
  costs: ReportCostItem[];
}

export const CostBreakdownCard: React.FC<CostBreakdownCardProps> = ({
  costs,
}) => {
  const totalCost = costs
    .filter((c) => c.record_type === "cost")
    .reduce((sum, c) => sum + parseFloat(c.amount), 0);
  const totalIncome = costs
    .filter((c) => c.record_type === "income")
    .reduce((sum, c) => sum + parseFloat(c.amount), 0);
  const netProfit = totalIncome - totalCost;

  // 按分类聚合支出
  const costByCategory: Record<string, number> = {};
  costs
    .filter((c) => c.record_type === "cost")
    .forEach((c) => {
      costByCategory[c.category] =
        (costByCategory[c.category] || 0) + parseFloat(c.amount);
    });

  const maxAmount = Math.max(...Object.values(costByCategory), 1);

  return (
    <View style={styles.card}>
      {/* 总览 */}
      <View style={styles.summaryRow}>
        <View style={styles.summaryItem}>
          <Text
            style={[styles.summaryValue, { color: colors.expense }]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.5}
          >
            {formatCompactNumber(totalCost)}
          </Text>
          <Text style={styles.summaryLabel}>总支出</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.summaryItem}>
          <Text
            style={[styles.summaryValue, { color: colors.income }]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.5}
          >
            {formatCompactNumber(totalIncome)}
          </Text>
          <Text style={styles.summaryLabel}>总收入</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.summaryItem}>
          <Text
            style={[
              styles.summaryValue,
              { color: netProfit >= 0 ? colors.income : colors.expense },
            ]}
            numberOfLines={1}
            adjustsFontSizeToFit
            minimumFontScale={0.5}
          >
            {netProfit >= 0 ? "+" : ""}
            {formatCompactNumber(netProfit)}
          </Text>
          <Text style={styles.summaryLabel}>净利润</Text>
        </View>
      </View>

      {/* 分类明细 */}
      {Object.entries(costByCategory).length > 0 && (
        <View style={styles.breakdown}>
          <Text style={styles.breakdownTitle}>支出分类</Text>
          {Object.entries(costByCategory).map(([category, amount]) => {
            const percent = (amount / maxAmount) * 100;
            return (
              <View key={category} style={styles.breakdownItem}>
                <View style={styles.breakdownRow}>
                  <Text style={styles.breakdownLabel}>{category}</Text>
                  <Text style={styles.breakdownValue}>{amount.toFixed(0)}</Text>
                </View>
                <View style={styles.barTrack}>
                  <View
                    style={[styles.barFill, { width: `${percent}%` }]}
                  />
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xxl,
    padding: spacing.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingBottom: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  summaryItem: {
    flex: 1,
    alignItems: "center",
  },
  summaryValue: {
    fontSize: fontSize.xl,
    fontWeight: "800",
    marginBottom: 2,
  },
  summaryLabel: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
  divider: {
    width: 1,
    height: 32,
    backgroundColor: colors.borderLight,
  },
  breakdown: {
    marginTop: spacing.lg,
  },
  breakdownTitle: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textSecondary,
    marginBottom: spacing.md,
    letterSpacing: 0.5,
  },
  breakdownItem: {
    marginBottom: spacing.md,
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  breakdownLabel: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  breakdownValue: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.text,
  },
  barTrack: {
    height: 4,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
    opacity: 0.6,
  },
});
