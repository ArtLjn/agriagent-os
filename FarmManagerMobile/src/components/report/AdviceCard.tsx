import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
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
              style={[
                styles.priorityBadge,
                { backgroundColor: config.bgColor },
              ]}
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
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  adviceItem: {
    flexDirection: "row",
    paddingBottom: spacingV2.md,
    marginBottom: spacingV2.md,
    borderBottomWidth: 1,
    borderBottomColor: farmTheme.colors.line,
  },
  adviceItemLast: {
    paddingBottom: 0,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  priorityBadge: {
    width: 32,
    height: 32,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacingV2.md,
  },
  adviceContent: {
    flex: 1,
  },
  adviceHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.xs,
  },
  adviceTitle: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.text,
  },
  priorityLabel: {
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
  },
  priorityText: {
    fontSize: fontSizeV2.xs,
    fontWeight: "900",
  },
  adviceDetail: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
});
