import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { ReportAdviceItem } from "../../api/types";

interface AdviceCardProps {
  items: ReportAdviceItem[];
}

const priorityConfig: Record<
  number,
  { label: string; color: string; bgColor: string; icon: string }
> = {
  1: {
    label: "高",
    color: colors.danger,
    bgColor: colors.dangerLight,
    icon: "alert-circle",
  },
  2: {
    label: "中",
    color: colors.warning,
    bgColor: colors.warningLight,
    icon: "information",
  },
  3: {
    label: "低",
    color: colors.info,
    bgColor: colors.infoLight,
    icon: "lightbulb-outline",
  },
};

export const AdviceCard: React.FC<AdviceCardProps> = ({ items }) => {
  return (
    <View style={styles.card}>
      {items.map((item, index) => {
        const config = priorityConfig[item.priority] || priorityConfig[2];
        return (
          <View
            key={index}
            style={[
              styles.adviceItem,
              index === items.length - 1 && styles.adviceItemLast,
            ]}
          >
            <View
              style={[styles.priorityBadge, { backgroundColor: config.bgColor }]}
            >
              <Icon name={config.icon} size={14} color={config.color} />
            </View>
            <View style={styles.adviceContent}>
              <View style={styles.adviceHeader}>
                <Text style={styles.adviceTitle}>{item.title}</Text>
                <View
                  style={[
                    styles.priorityLabel,
                    { backgroundColor: config.bgColor },
                  ]}
                >
                  <Text style={[styles.priorityText, { color: config.color }]}>
                    {config.label}
                  </Text>
                </View>
              </View>
              <Text style={styles.adviceDetail}>{item.detail}</Text>
            </View>
          </View>
        );
      })}
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
  adviceItem: {
    flexDirection: "row",
    paddingBottom: spacing.md,
    marginBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  adviceItemLast: {
    paddingBottom: 0,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  priorityBadge: {
    width: 32,
    height: 32,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  adviceContent: {
    flex: 1,
  },
  adviceHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  adviceTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.text,
  },
  priorityLabel: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  priorityText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
  },
  adviceDetail: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
