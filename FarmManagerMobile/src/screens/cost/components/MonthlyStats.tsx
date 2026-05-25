import React from 'react';
import {View, Text, StyleSheet, TouchableOpacity} from 'react-native';
import dayjs from 'dayjs';
// import DateTimePicker, {DateTimePickerEvent} from '@react-native-community/datetimepicker';
import {Card} from '../../../components/Card';
import {colors} from '../../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface MonthlyStatsProps {
  selectedMonth: Date;
  stats: {cost: number; income: number; balance: number};
  onPreviousMonth?: () => void;
  onNextMonth?: () => void;
}

export const MonthlyStats: React.FC<MonthlyStatsProps> = ({
  selectedMonth,
  stats,
  onPreviousMonth,
  onNextMonth,
}) => (
  <View style={styles.statsSection}>
    <View style={styles.monthSelector}>
      <TouchableOpacity
        onPress={onPreviousMonth}
        style={styles.monthButton}
        hitSlop={{top: 10, bottom: 10, left: 10, right: 10}}>
        <Icon name="chevron-left" size={24} color={colors.primary} />
      </TouchableOpacity>
      <Icon name="calendar-month" size={20} color={colors.primary} />
      <Text style={styles.monthText}>{dayjs(selectedMonth).format('YYYY年M月')}</Text>
      <TouchableOpacity
        onPress={onNextMonth}
        style={styles.monthButton}
        hitSlop={{top: 10, bottom: 10, left: 10, right: 10}}>
        <Icon name="chevron-right" size={24} color={colors.primary} />
      </TouchableOpacity>
    </View>
    <View style={styles.statsCards}>
      <Card style={[styles.statCard, styles.statCardCost]} padding="lg">
        <Text style={styles.statLabel}>支出</Text>
        <Text style={[styles.statValue, {color: colors.danger}]}>
          {stats.cost.toFixed(2)}
        </Text>
      </Card>
      <Card style={[styles.statCard, styles.statCardIncome]} padding="lg">
        <Text style={styles.statLabel}>收入</Text>
        <Text style={[styles.statValue, {color: colors.success}]}>
          {stats.income.toFixed(2)}
        </Text>
      </Card>
      <Card style={[styles.statCard, styles.statCardBalance]} padding="lg">
        <Text style={styles.statLabel}>结余</Text>
        <Text
          style={[
            styles.statValue,
            {color: stats.balance >= 0 ? colors.success : colors.danger},
          ]}
        >
          {stats.balance.toFixed(2)}
        </Text>
      </Card>
    </View>
  </View>
);

const styles = StyleSheet.create({
  statsSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
  },
  monthSelector: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  monthButton: {
    padding: spacing.sm,
  },
  monthText: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.primary,
  },
  statsCards: {
    flexDirection: 'row',
    gap: spacing.sm,
  },
  statCard: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.md,
  },
  statCardCost: {
    borderTopWidth: 3,
    borderTopColor: colors.danger,
  },
  statCardIncome: {
    borderTopWidth: 3,
    borderTopColor: colors.success,
  },
  statCardBalance: {
    borderTopWidth: 3,
    borderTopColor: colors.primary,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  statValue: {
    fontSize: fontSize.lg,
    fontWeight: '800',
  },
});
