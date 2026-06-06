import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
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
      <View style={styles.glow} />
      <View style={styles.topRow}>
        <View style={styles.badge}>
          <Icon name={iconName} size={15} color="#FFFFFF" />
          <Text style={styles.badgeText}>{typeLabel}</Text>
        </View>
        <View style={styles.iconPlate}>
          <Icon name="file-chart-outline" size={28} color="#FFFFFF" />
        </View>
      </View>
      <Text style={styles.title}>农事复盘报告</Text>
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
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  glow: {
    position: "absolute",
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: "rgba(216, 240, 188, 0.14)",
    right: -46,
    top: -48,
  },
  topRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.14)",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
  },
  badgeText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  iconPlate: {
    width: 52,
    height: 52,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255, 255, 255, 0.14)",
  },
  title: {
    fontSize: 25,
    lineHeight: 31,
    fontWeight: "900",
    color: "#FFFFFF",
    marginBottom: spacingV2.sm,
  },
  period: {
    fontSize: fontSizeV2.md,
    fontWeight: "800",
    color: "rgba(255, 255, 255, 0.78)",
    marginBottom: spacingV2.xs,
  },
  date: {
    fontSize: fontSizeV2.xs,
    color: "rgba(255, 255, 255, 0.62)",
    fontWeight: "600",
  },
});
