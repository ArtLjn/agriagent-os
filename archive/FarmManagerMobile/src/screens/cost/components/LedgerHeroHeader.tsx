import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import dayjs from "dayjs";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface LedgerHeroHeaderProps {
  selectedMonth: Date;
  onPreviousMonth?: () => void;
  onNextMonth?: () => void;
}

export const LedgerHeroHeader: React.FC<LedgerHeroHeaderProps> = ({
  selectedMonth,
  onPreviousMonth,
  onNextMonth,
}) => (
  <View style={styles.header}>
    <View style={styles.titleGroup}>
      <Text style={styles.title}>本月账本</Text>
    </View>
    <View style={styles.monthPill}>
      <TouchableOpacity
        onPress={onPreviousMonth}
        style={styles.monthButton}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Icon name="chevron-left" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={styles.monthText}>
        {dayjs(selectedMonth).format("YYYY年M月")}
      </Text>
      <TouchableOpacity
        onPress={onNextMonth}
        style={styles.monthButton}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Icon name="chevron-right" size={18} color={colors.textSecondary} />
      </TouchableOpacity>
    </View>
  </View>
);

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
  },
  titleGroup: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    fontSize: fontSizeV2.xl,
    lineHeight: 28,
    color: colors.text,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  monthPill: {
    height: 40,
    paddingHorizontal: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    backgroundColor: colors.surface,
  },
  monthButton: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  monthText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
});
