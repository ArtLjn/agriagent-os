import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { spacing, fontSize } from "../theme/spacing";

interface TimelineItem {
  id: string;
  title: string;
  subtitle: string;
  dateRange: string;
  isCurrent?: boolean;
}

interface TimelineProps {
  items: TimelineItem[];
}

export const Timeline: React.FC<TimelineProps> = ({ items }) => {
  return (
    <View style={styles.container}>
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        return (
          <View key={item.id} style={styles.row}>
            <View style={styles.leftColumn}>
              <View style={[styles.dot, item.isCurrent && styles.dotCurrent]} />
              {!isLast && <View style={styles.line} />}
            </View>

            <View
              style={[
                styles.contentCard,
                item.isCurrent && styles.contentCardCurrent,
              ]}
            >
              <Text
                style={[styles.title, item.isCurrent && styles.titleCurrent]}
              >
                {item.title}
              </Text>
              <Text style={styles.subtitle}>{item.subtitle}</Text>
              <Text style={styles.dateRange}>{item.dateRange}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  row: {
    flexDirection: "row",
  },
  leftColumn: {
    width: 24,
    alignItems: "center",
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.border,
    borderWidth: 2,
    borderColor: colors.border,
  },
  dotCurrent: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
  },
  contentCard: {
    flex: 1,
    marginLeft: spacing.sm,
    marginBottom: spacing.md,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: 8,
    borderLeftWidth: 3,
    borderLeftColor: "transparent",
  },
  contentCardCurrent: {
    backgroundColor: colors.primaryLight,
    borderLeftColor: colors.primary,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.text,
    marginBottom: spacing.xs,
  },
  titleCurrent: {
    color: colors.primary,
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  dateRange: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
