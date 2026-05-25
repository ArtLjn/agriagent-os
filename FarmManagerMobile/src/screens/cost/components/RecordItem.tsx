import React from 'react';
import {View, Text, TouchableOpacity, StyleSheet} from 'react-native';
import type {CostRecord} from '../../../api/types';
import {Card} from '../../../components/Card';
import {colors} from '../../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const TYPE_CONFIG: Record<string, {label: string; color: string; icon: string; bgColor: string}> = {
  cost: {label: '支出', color: colors.danger, icon: 'arrow-down-circle', bgColor: colors.dangerLight},
  income: {label: '收入', color: colors.success, icon: 'arrow-up-circle', bgColor: colors.successLight},
};

const CATEGORY_ICONS: Record<string, string> = {
  '种子': 'seed',
  '化肥': 'flask',
  '农药': 'spray',
  '人工': 'account-hard-hat',
  '水电': 'flash',
  '地租': 'home-variant',
  '销售': 'cash',
  '补贴': 'gift',
  '其他': 'dots-horizontal',
};

interface RecordItemProps {
  item: CostRecord;
  onPress: () => void;
}

export const RecordItem: React.FC<RecordItemProps> = ({item, onPress}) => {
  const config = TYPE_CONFIG[item.record_type] || {
    label: item.record_type,
    color: colors.textSecondary,
    icon: 'help-circle',
    bgColor: colors.surfaceMuted,
  };
  const catIcon = CATEGORY_ICONS[item.category] || 'tag';
  const isCost = item.record_type === 'cost';
  const prefix = isCost ? '-' : '+';

  return (
    <TouchableOpacity onPress={onPress} delayLongPress={500} activeOpacity={0.7}>
      <Card style={styles.card}>
        <View style={styles.row}>
          <View style={styles.left}>
            <View style={styles.categoryRow}>
              <View style={[styles.typeIcon, {backgroundColor: config.bgColor}]}>
                <Icon name={catIcon} size={18} color={config.color} />
              </View>
              <View>
                <Text style={styles.category}>{item.category}</Text>
                <Text style={styles.date}>{item.record_date}</Text>
              </View>
            </View>
          </View>
          <View style={styles.right}>
            <Text style={[styles.amount, {color: config.color}]}>
              {prefix}
              {item.amount}
            </Text>
            <View style={[styles.typeBadge, {backgroundColor: config.bgColor}]}>
              <Text style={[styles.typeText, {color: config.color}]}>{config.label}</Text>
            </View>
          </View>
        </View>
        {item.note ? (
          <View style={styles.noteRow}>
            <Icon name="note-text-outline" size={12} color={colors.textTertiary} />
            <Text style={styles.note} numberOfLines={1}>
              {item.note}
            </Text>
          </View>
        ) : null}
      </Card>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  left: {
    flex: 1,
  },
  categoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  typeIcon: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  category: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  right: {
    alignItems: 'flex-end',
  },
  amount: {
    fontSize: fontSize.lg,
    fontWeight: '800',
  },
  typeBadge: {
    marginTop: spacing.xs,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  typeText: {
    fontSize: fontSize.xs,
    fontWeight: '700',
  },
  noteRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    gap: spacing.xs,
  },
  note: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    flex: 1,
  },
});
