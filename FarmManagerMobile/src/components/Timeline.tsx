import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";

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
              <View
                style={[
                  styles.dot,
                  item.isCurrent && styles.dotCurrent,
                ]}
              />
              {!isLast && (
                <View
                  style={[
                    styles.line,
                    item.isCurrent && styles.lineActive,
                  ]}
                />
              )}
            </View>

            <View
              style={[
                styles.contentCard,
                item.isCurrent && styles.contentCardCurrent,
              ]}
            >
              <Text
                style={[
                  styles.title,
                  item.isCurrent && styles.titleCurrent,
                ]}
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
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.sm,
  },
  row: {
    flexDirection: "row",
  },
  leftColumn: {
    width: 24,
    alignItems: "center",
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.border,
    borderWidth: 2,
    borderColor: colors.borderLight,
  },
  dotCurrent: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  line: {
    width: 2,
    flex: 1,
    backgroundColor: colors.borderLight,
    marginVertical: spacingV2.xs,
  },
  lineActive: {
    backgroundColor: "rgba(74, 123, 247, 0.2)",
  },
  contentCard: {
    flex: 1,
    marginLeft: spacingV2.md,
    marginBottom: spacingV2.lg,
    padding: spacingV2.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
  },
  contentCardCurrent: {
    backgroundColor: colors.primaryMuted,
  },
  title: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    marginBottom: spacingV2.xs,
  },
  titleCurrent: {
    color: colors.primary,
  },
  subtitle: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginBottom: spacingV2.xs,
    lineHeight: 20,
  },
  dateRange: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
});
