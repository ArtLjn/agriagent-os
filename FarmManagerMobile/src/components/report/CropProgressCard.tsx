import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { ReportCycleItem } from "../../api/types";

interface CropProgressCardProps {
  data: ReportCycleItem;
}

export const CropProgressCard: React.FC<CropProgressCardProps> = ({ data }) => {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.name}>{data.name}</Text>
          {data.field_name && (
            <View style={styles.fieldBadge}>
              <Text style={styles.fieldText}>{data.field_name}</Text>
            </View>
          )}
        </View>
        <Text style={styles.stage}>
          {data.current_stage} · 第 {data.current_stage_index}/
          {data.total_stages} 阶段
        </Text>
      </View>

      <View style={styles.progressRow}>
        <View style={styles.progressTrack}>
          <View
            style={[
              styles.progressFill,
              { width: `${data.progress_percent}%` },
            ]}
          />
        </View>
        <Text style={styles.progressText}>{data.progress_percent}%</Text>
      </View>

      <View style={styles.footer}>
        <View style={styles.footerItem}>
          <Icon name="calendar-clock" size={13} color={colors.textTertiary} />
          <Text style={styles.footerText}>已种植 {data.days_elapsed} 天</Text>
        </View>
        <View style={styles.footerItem}>
          <Icon name="tools" size={13} color={colors.textTertiary} />
          <Text style={styles.footerText}>
            本周期 {data.period_log_count} 次农事
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  header: {
    marginBottom: spacingV2.md,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    marginBottom: spacingV2.xs,
  },
  name: {
    fontSize: fontSizeV2.lg,
    fontWeight: "900",
    color: colors.text,
  },
  fieldBadge: {
    backgroundColor: farmTheme.colors.surfaceSoft,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
  },
  fieldText: {
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  stage: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    marginBottom: spacingV2.md,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    backgroundColor: farmTheme.colors.surfaceSoft,
    borderRadius: borderRadiusV2.full,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: farmTheme.colors.leaf,
    borderRadius: borderRadiusV2.full,
  },
  progressText: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: farmTheme.colors.leaf,
    minWidth: 40,
    textAlign: "right",
  },
  footer: {
    flexDirection: "row",
    gap: spacingV2.lg,
  },
  footerItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  footerText: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
});
