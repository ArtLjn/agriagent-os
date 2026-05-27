import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import dayjs from "dayjs";
import { colors } from "../../../theme/colors";
import { spacing, fontSize } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface MonthlyStatsProps {
  selectedMonth: Date;
  onPreviousMonth?: () => void;
  onNextMonth?: () => void;
}

export const MonthlyStats: React.FC<MonthlyStatsProps> = ({
  selectedMonth,
  onPreviousMonth,
  onNextMonth,
}) => (
  <View style={styles.statsSection}>
    <View style={styles.monthSelector}>
      <TouchableOpacity
        onPress={onPreviousMonth}
        style={styles.monthButton}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Icon name="chevron-left" size={24} color={colors.primary} />
      </TouchableOpacity>
      <Icon name="calendar-month" size={20} color={colors.primary} />
      <Text style={styles.monthText}>
        {dayjs(selectedMonth).format("YYYY年M月")}
      </Text>
      <TouchableOpacity
        onPress={onNextMonth}
        style={styles.monthButton}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Icon name="chevron-right" size={24} color={colors.primary} />
      </TouchableOpacity>
    </View>
  </View>
);

const styles = StyleSheet.create({
  statsSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  monthSelector: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  monthButton: {
    padding: spacing.md,
    minWidth: 48,
    minHeight: 48,
    justifyContent: "center",
    alignItems: "center",
  },
  monthText: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.primary,
  },
});
