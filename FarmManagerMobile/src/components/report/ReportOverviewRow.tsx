import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { formatCompactNumber } from "../../utils/numberFormat";
import type { ReportOverviewMetrics } from "../../api/types";

interface ReportOverviewRowProps {
  metrics: ReportOverviewMetrics;
}

interface MetricCardProps {
  icon: string;
  label: string;
  value: string;
  color: string;
  bgColor: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  label,
  value,
  color,
  bgColor,
}) => (
  <View style={[styles.card, { backgroundColor: bgColor }]}>
    <Icon name={icon} size={18} color={color} style={styles.icon} />
    <Text
      style={[styles.value, { color }]}
      numberOfLines={1}
      adjustsFontSizeToFit
      minimumFontScale={0.4}
    >
      {value}
    </Text>
    <Text style={styles.label}>{label}</Text>
  </View>
);

export const ReportOverviewRow: React.FC<ReportOverviewRowProps> = ({
  metrics,
}) => {
  const profitColor =
    parseFloat(metrics.net_profit) >= 0 ? colors.income : colors.expense;
  const profitBg =
    parseFloat(metrics.net_profit) >= 0
      ? colors.incomeBg
      : colors.expenseBg;

  return (
    <View style={styles.container}>
      <MetricCard
        icon="sprout"
        label="活跃茬口"
        value={String(metrics.active_cycles)}
        color={colors.success}
        bgColor={colors.successMuted}
      />
      <MetricCard
        icon="tools"
        label="农事次数"
        value={String(metrics.log_count)}
        color={colors.info}
        bgColor={colors.infoLight}
      />
      <MetricCard
        icon="cash-minus"
        label="净支出"
        value={formatCompactNumber(parseFloat(metrics.total_cost))}
        color={colors.expense}
        bgColor={colors.expenseBg}
      />
      <MetricCard
        icon="chart-line"
        label="净利润"
        value={formatCompactNumber(parseFloat(metrics.net_profit))}
        color={profitColor}
        bgColor={profitBg}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.xl,
  },
  card: {
    flex: 1,
    alignItems: "center",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.xl,
  },
  icon: {
    marginBottom: spacing.sm,
  },
  value: {
    fontSize: fontSize.lg,
    fontWeight: "800",
    marginBottom: 2,
  },
  label: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    fontWeight: "600",
  },
});
