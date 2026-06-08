import React from "react";
import { View, Text, StyleSheet } from "react-native";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";
import { formatRecordAmount } from "../utils/recordDisplay";

interface LedgerSummaryCardProps {
  income: number;
  cost: number;
  count: number;
}

export const LedgerSummaryCard: React.FC<LedgerSummaryCardProps> = ({
  income,
  cost,
  count,
}) => {
  const balance = income - cost;
  const isPositive = balance >= 0;
  const hasData = count > 0;

  return (
    <View style={styles.card}>
      <View style={styles.topRow}>
        <View>
          <Text style={styles.label}>本月结余</Text>
          {hasData ? (
            <Text style={[styles.balance, { color: colors.text }]}>
              {isPositive ? "+" : "-"}
              {formatRecordAmount(String(Math.abs(balance)))}
            </Text>
          ) : (
            <Text style={styles.balancePlaceholder}>暂无数据</Text>
          )}
        </View>
        <View style={styles.countBadge}>
          <Text style={styles.countText}>{count} 条</Text>
        </View>
      </View>

      <View style={styles.divider} />

      <View style={styles.statsRow}>
        <View style={styles.statItem}>
          <View style={[styles.dot, { backgroundColor: colors.income }]} />
          <Text style={styles.statLabel}>收入</Text>
          <Text style={[styles.statValue, { color: colors.income }]}>
            {hasData ? `+${formatRecordAmount(String(income))}` : "-"}
          </Text>
        </View>
        <View style={styles.statDivider} />
        <View style={styles.statItem}>
          <View style={[styles.dot, { backgroundColor: colors.expense }]} />
          <Text style={styles.statLabel}>支出</Text>
          <Text style={[styles.statValue, { color: colors.expense }]}>
            {hasData ? `-${formatRecordAmount(String(cost))}` : "-"}
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    padding: spacingV2.lg,
    borderRadius: borderRadiusV2.xxxl,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 3,
  },
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacingV2.md,
  },
  label: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
    letterSpacing: -0.2,
  },
  balance: {
    marginTop: spacingV2.xs,
    fontSize: 36,
    lineHeight: 42,
    fontWeight: "800",
    letterSpacing: -1,
  },
  balancePlaceholder: {
    marginTop: spacingV2.xs,
    fontSize: 28,
    lineHeight: 36,
    fontWeight: "700",
    color: colors.textTertiary,
    letterSpacing: -0.5,
  },
  countBadge: {
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.xs,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surfaceMuted,
  },
  countText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  divider: {
    height: 1,
    backgroundColor: "rgba(0,0,0,0.04)",
    marginBottom: spacingV2.md,
  },
  statsRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  statItem: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
  },
  statDivider: {
    width: 1,
    height: 20,
    backgroundColor: "rgba(0,0,0,0.06)",
    marginHorizontal: spacingV2.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  statValue: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
});
