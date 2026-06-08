import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { ReportLogItem } from "../../api/types";

interface FarmLogListCardProps {
  logs: ReportLogItem[];
}

export const FarmLogListCard: React.FC<FarmLogListCardProps> = ({ logs }) => {
  const formatDate = (d: string) => {
    const date = new Date(d);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  return (
    <View style={styles.card}>
      {logs.map((log, index) => (
        <View
          key={index}
          style={[
            styles.logItem,
            index === logs.length - 1 && styles.logItemLast,
          ]}
        >
          <View style={styles.timelineDot} />
          <View style={styles.logContent}>
            <View style={styles.logHeader}>
              <Text style={styles.logType}>{log.operation_type}</Text>
              <Text style={styles.logDate}>{formatDate(log.operation_date)}</Text>
            </View>
            {log.cycle_name && (
              <Text style={styles.logCycle}>{log.cycle_name}</Text>
            )}
            {log.note && (
              <Text style={styles.logNote} numberOfLines={2}>
                {log.note}
              </Text>
            )}
          </View>
        </View>
      ))}
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
  logItem: {
    flexDirection: "row",
    paddingBottom: spacing.md,
    marginBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  logItemLast: {
    paddingBottom: 0,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
    marginTop: 6,
    marginRight: spacing.md,
  },
  logContent: {
    flex: 1,
  },
  logHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  logType: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
  },
  logDate: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
  },
  logCycle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  logNote: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    lineHeight: 20,
  },
});
