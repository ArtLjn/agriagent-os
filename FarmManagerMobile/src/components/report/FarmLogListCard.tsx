import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
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
              <Text style={styles.logDate}>
                {formatDate(log.operation_date)}
              </Text>
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
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  logItem: {
    flexDirection: "row",
    paddingBottom: spacingV2.md,
    marginBottom: spacingV2.md,
    borderBottomWidth: 1,
    borderBottomColor: farmTheme.colors.line,
  },
  logItemLast: {
    paddingBottom: 0,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  timelineDot: {
    width: 8,
    height: 8,
    borderRadius: borderRadiusV2.full,
    backgroundColor: farmTheme.colors.leaf,
    marginTop: 6,
    marginRight: spacingV2.md,
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
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.text,
  },
  logDate: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
  },
  logCycle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: 2,
  },
  logNote: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    lineHeight: 20,
  },
});
