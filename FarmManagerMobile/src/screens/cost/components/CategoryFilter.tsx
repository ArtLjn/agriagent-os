import React from 'react';
import {View, Text, ScrollView, TouchableOpacity, StyleSheet} from 'react-native';
import {colors} from '../../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../../theme/spacing';

interface CategoryFilterProps {
  categoryList: string[];
  categoryStats: Record<string, {cost: number; income: number}>;
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
      style={[styles.categoryChip, selectedCategory === null && styles.categoryChipActive]}
      onPress={() => onSelectCategory(null)}>
      <Text
        style={[
          styles.categoryChipText,
          selectedCategory === null && styles.categoryChipTextActive,
        ]}>
        全部
      </Text>
    </TouchableOpacity>
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      {categoryList.map(cat => {
        const catStats = categoryStats[cat];
        const isActive = selectedCategory === cat;
        return (
          <TouchableOpacity
            key={cat}
            style={[styles.categoryChip, isActive && styles.categoryChipActive]}
            onPress={() => onSelectCategory(cat)}>
            <Text
              style={[
                styles.categoryChipText,
                isActive && styles.categoryChipTextActive,
              ]}>
              {cat}
            </Text>
            {catStats && (catStats.cost > 0 || catStats.income > 0) && (
              <Text
                style={[
                  styles.categoryChipAmount,
                  isActive && styles.categoryChipAmountActive,
                ]}>
                {catStats.cost > 0 ? `-${catStats.cost.toFixed(0)}` : ''}
                {catStats.income > 0 ? `+${catStats.income.toFixed(0)}` : ''}
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
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  categoryChip: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginRight: spacing.xs,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  categoryChipActive: {
    backgroundColor: colors.primaryMuted,
    borderColor: colors.primary,
  },
  categoryChipText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  categoryChipTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  categoryChipAmount: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginLeft: spacing.xs,
  },
  categoryChipAmountActive: {
    color: colors.primary,
  },
});
