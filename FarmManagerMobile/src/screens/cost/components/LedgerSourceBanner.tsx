import React from "react";
import { View, Text, StyleSheet } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface LedgerSourceBannerProps {
  title?: string;
  cycleId?: number;
  category?: string;
  sourceType?: string;
}

function formatSourceType(sourceType?: string): string | null {
  if (sourceType === "labor_entry") {
    return "来自工资记录";
  }
  if (sourceType === "operation_work_order") {
    return "来自农事作业";
  }
  return sourceType || null;
}

export const LedgerSourceBanner: React.FC<LedgerSourceBannerProps> = ({
  title,
  cycleId,
  category,
  sourceType,
}) => {
  const summary = [
    cycleId ? `茬口 ${cycleId}` : null,
    category || null,
    formatSourceType(sourceType),
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <View style={styles.banner}>
      <View style={styles.icon}>
        <Icon name="filter-check-outline" size={18} color={colors.primary} />
      </View>
      <View style={styles.info}>
        <Text style={styles.title}>{title || "已应用来源筛选"}</Text>
        {summary ? <Text style={styles.text}>{summary}</Text> : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  banner: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.lg,
    padding: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.primaryMuted,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  icon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "800",
  },
  text: {
    marginTop: 2,
    fontSize: fontSizeV2.xs,
    color: colors.textSecondary,
    fontWeight: "600",
  },
});
