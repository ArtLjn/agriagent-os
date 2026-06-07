import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";
import type { DateRangeFilter, RecordFilterType } from "../utils/recordDisplay";

interface LedgerFiltersProps {
  filter: RecordFilterType;
  dateRange: DateRangeFilter;
  categoryList: string[];
  categoryFilter: string | null;
  onFilterChange: (filter: RecordFilterType) => void;
  onDateRangeChange: (range: DateRangeFilter) => void;
  onCategoryFilterChange: (category: string | null) => void;
}

const TYPE_FILTERS: { key: RecordFilterType; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "cost", label: "支出" },
  { key: "income", label: "收入" },
  { key: "debt", label: "赊账" },
];

const DATE_FILTERS: { key: DateRangeFilter; label: string; icon?: string }[] = [
  { key: "month", label: "本月", icon: "calendar-month-outline" },
  { key: "today", label: "今天" },
  { key: "week", label: "近7天" },
  { key: "all", label: "筛选", icon: "tune-variant" },
];

export const LedgerFilters: React.FC<LedgerFiltersProps> = ({
  filter,
  dateRange,
  categoryList,
  categoryFilter,
  onFilterChange,
  onDateRangeChange,
  onCategoryFilterChange,
}) => (
  <View style={styles.container}>
    <View style={styles.segment}>
      {TYPE_FILTERS.map((item) => {
        const active = filter === item.key;
        return (
          <TouchableOpacity
            key={item.key}
            style={[
              styles.segmentButton,
              active && styles.segmentButtonActive,
            ]}
            onPress={() => onFilterChange(item.key)}
            activeOpacity={0.75}
          >
            <Text
              style={[
                styles.segmentText,
                active && styles.segmentTextActive,
              ]}
            >
              {item.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>

    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.quickContent}
    >
      {DATE_FILTERS.map((item) => {
        const active = dateRange === item.key;
        return (
          <TouchableOpacity
            key={item.key}
            style={[
              styles.quickChip,
              active && styles.quickChipActive,
            ]}
            onPress={() => onDateRangeChange(item.key)}
            activeOpacity={0.75}
          >
            {item.icon ? (
              <Icon
                name={item.icon}
                size={15}
                color={active ? colors.primary : colors.textTertiary}
              />
            ) : null}
            <Text
              style={[
                styles.quickText,
                active && styles.quickTextActive,
              ]}
            >
              {item.label}
            </Text>
          </TouchableOpacity>
        );
      })}
      {categoryList.slice(0, 8).map((cat) => {
        const active = categoryFilter === cat;
        return (
          <TouchableOpacity
            key={cat}
            style={[
              styles.quickChip,
              active && styles.quickChipActive,
            ]}
            onPress={() => onCategoryFilterChange(active ? null : cat)}
            activeOpacity={0.75}
          >
            <Text
              style={[
                styles.quickText,
                active && styles.quickTextActive,
              ]}
            >
              {cat}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  </View>
);

const styles = StyleSheet.create({
  container: {
    marginBottom: spacingV2.lg,
  },
  segment: {
    marginHorizontal: spacingV2.lg,
    height: 42,
    flexDirection: "row",
    gap: spacingV2.xs,
    padding: spacingV2.xs,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.surfaceMuted,
  },
  segmentButton: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: borderRadiusV2.lg,
  },
  segmentButtonActive: {
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 1,
  },
  segmentText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  segmentTextActive: {
    color: colors.text,
    fontWeight: "700",
  },
  quickContent: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    gap: spacingV2.sm,
    alignItems: "center",
  },
  quickChip: {
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  quickChipActive: {
    backgroundColor: colors.primaryMuted,
    borderColor: colors.primary,
  },
  quickText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  quickTextActive: {
    color: colors.primary,
    fontWeight: "700",
  },
});
