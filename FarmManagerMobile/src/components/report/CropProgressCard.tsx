import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { ReportCycleItem } from "../../api/types";

interface CropProgressCardProps {
  data: ReportCycleItem;
}

export const CropProgressCard: React.FC<CropProgressCardProps> = ({
  data,
}) => {
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
          {data.current_stage} · 第 {data.current_stage_index}/{data.total_stages} 阶段
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
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xxl,
    padding: spacing.lg,
    marginBottom: spacing.md,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  header: {
    marginBottom: spacing.md,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.xs,
  },
  name: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  fieldBadge: {
    backgroundColor: colors.surfaceMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  fieldText: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  stage: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
  },
  progressText: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.primary,
    minWidth: 40,
    textAlign: "right",
  },
  footer: {
    flexDirection: "row",
    gap: spacing.lg,
  },
  footerItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  footerText: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
});
