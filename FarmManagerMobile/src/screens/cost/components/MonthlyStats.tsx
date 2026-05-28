import React from "react";
import { View, Text, StyleSheet, TouchableOpacity } from "react-native";
import dayjs from "dayjs";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2 } from "../../../theme/spacing";
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
        <Icon name="chevron-left" size={20} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={styles.monthText}>
        {dayjs(selectedMonth).format("YYYY年M月")}
      </Text>
      <TouchableOpacity
        onPress={onNextMonth}
        style={styles.monthButton}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
      >
        <Icon name="chevron-right" size={20} color={colors.textSecondary} />
      </TouchableOpacity>
    </View>
  </View>
);

const styles = StyleSheet.create({
  statsSection: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.sm,
  },
  monthSelector: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.sm,
  },
  monthButton: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.surfaceMuted,
    justifyContent: "center",
    alignItems: "center",
  },
  monthText: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.3,
    minWidth: 120,
    textAlign: "center",
  },
});
