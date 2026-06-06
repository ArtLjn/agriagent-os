import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface ReportHeaderProps {
  reportType: string;
  periodStart: string;
  periodEnd: string;
  createdAt: string;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({
  reportType,
  periodStart,
  periodEnd,
  createdAt,
}) => {
  const isWeekly = reportType === "weekly";
  const typeLabel = isWeekly ? "周报" : "月报";
  const iconName = isWeekly ? "calendar-week" : "calendar-month";

  const formatDate = (d: string) => {
    const date = new Date(d);
    return `${date.getMonth() + 1}月${date.getDate()}日`;
  };

  return (
    <View style={styles.container}>
      <View style={styles.badge}>
        <Icon name={iconName} size={14} color={colors.primary} />
        <Text style={styles.badgeText}>{typeLabel}</Text>
      </View>
      <Text style={styles.period}>
        {formatDate(periodStart)} ~ {formatDate(periodEnd)}
      </Text>
      <Text style={styles.date}>
        生成于 {new Date(createdAt).toLocaleDateString("zh-CN")}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.md,
  },
  badgeText: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.primary,
  },
  period: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacing.xs,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
});
