import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
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
                  <View style={[styles.barFill, { width: `${percent}%` }]} />
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
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  summaryRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingBottom: spacingV2.lg,
    borderBottomWidth: 1,
    borderBottomColor: farmTheme.colors.line,
  },
  summaryItem: {
    flex: 1,
    alignItems: "center",
  },
  summaryValue: {
    fontSize: fontSizeV2.xl,
    fontWeight: "900",
    marginBottom: 2,
  },
  summaryLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  divider: {
    width: 1,
    height: 32,
    backgroundColor: farmTheme.colors.line,
  },
  breakdown: {
    marginTop: spacingV2.lg,
  },
  breakdownTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "900",
    color: colors.textSecondary,
    marginBottom: spacingV2.md,
    letterSpacing: 0,
  },
  breakdownItem: {
    marginBottom: spacingV2.md,
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.xs,
  },
  breakdownLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  breakdownValue: {
    fontSize: fontSizeV2.sm,
    fontWeight: "900",
    color: colors.text,
  },
  barTrack: {
    height: 4,
    backgroundColor: farmTheme.colors.surfaceSoft,
    borderRadius: borderRadiusV2.full,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    backgroundColor: farmTheme.colors.leaf,
    borderRadius: borderRadiusV2.full,
    opacity: 0.78,
  },
});
