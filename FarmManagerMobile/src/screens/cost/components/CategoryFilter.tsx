import React from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";

interface CategoryFilterProps {
  categoryList: string[];
  categoryStats: Record<string, { cost: number; income: number }>;
  selectedCategory: string | null;
  onSelectCategory: (category: string | null) => void;
}

export const CategoryFilter: React.FC<CategoryFilterProps> = ({
  categoryList,
  categoryStats,
  selectedCategory,
  onSelectCategory,
}) => (
  <View style={styles.categoryFilterRow}>
    <TouchableOpacity
      style={[
        styles.categoryChip,
        selectedCategory === null && styles.categoryChipActive,
      ]}
      onPress={() => onSelectCategory(null)}
    >
      <Text
        style={[
          styles.categoryChipText,
          selectedCategory === null && styles.categoryChipTextActive,
        ]}
      >
        全部分类
      </Text>
    </TouchableOpacity>
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      {categoryList.map((cat) => {
        const catStats = categoryStats[cat];
        const isActive = selectedCategory === cat;
        return (
          <TouchableOpacity
            key={cat}
            style={[styles.categoryChip, isActive && styles.categoryChipActive]}
            onPress={() => onSelectCategory(cat)}
          >
            <Text
              style={[
                styles.categoryChipText,
                isActive && styles.categoryChipTextActive,
              ]}
            >
              {cat}
            </Text>
            {catStats && (catStats.cost > 0 || catStats.income > 0) && (
              <Text
                style={[
                  styles.categoryChipAmount,
                  isActive && styles.categoryChipAmountActive,
                ]}
              >
                {catStats.cost > 0 ? `-${catStats.cost.toFixed(0)}` : ""}
                {catStats.income > 0 ? `+${catStats.income.toFixed(0)}` : ""}
              </Text>
            )}
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  </View>
);

const styles = StyleSheet.create({
  categoryFilterRow: {
    flexDirection: "row",
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
    gap: spacingV2.sm,
  },
  categoryChip: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.full,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.xs,
    marginRight: spacingV2.xs,
    flexDirection: "row",
    alignItems: "center",
  },
  categoryChipActive: {
    backgroundColor: colors.primaryMuted,
  },
  categoryChipText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "500",
  },
  categoryChipTextActive: {
    color: colors.primary,
    fontWeight: "600",
  },
  categoryChipAmount: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
    marginLeft: spacingV2.xs,
  },
  categoryChipAmountActive: {
    color: colors.primary,
  },
});
