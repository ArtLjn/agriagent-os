import React, {useEffect, useMemo, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  Platform,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import DateTimePicker, {DateTimePickerEvent} from '@react-native-community/datetimepicker';
import {useCostStore} from '../../stores/costStore';
import type {CostRecord} from '../../api/types';
import {Card} from '../../components/Card';
import {EmptyState} from '../../components/EmptyState';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

type FilterType = 'all' | 'cost' | 'income';

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

type CostListNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  'CostCreate'
>;

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const {records, loading, fetchRecords, deleteRecord} = useCostStore();
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const currentMonth = dayjs(selectedMonth).format('YYYY-MM');

  const stats = useMemo(() => {
    const monthRecords = records.filter(r => r.record_date.startsWith(currentMonth));
    const cost = monthRecords
      .filter(r => r.record_type === 'cost')
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    const income = monthRecords
      .filter(r => r.record_type === 'income')
      .reduce((sum, r) => sum + parseFloat(r.amount), 0);
    return {cost, income, balance: income - cost};
  }, [records, currentMonth]);

  const categoryList = useMemo(() => {
    const categories = new Set(records.map(r => r.category));
    return Array.from(categories);
  }, [records]);

  const categoryStats = useMemo(() => {
    const monthRecords = records.filter(r => r.record_date.startsWith(currentMonth));
    const stats: Record<string, {cost: number; income: number}> = {};
    for (const r of monthRecords) {
      if (!stats[r.category]) stats[r.category] = {cost: 0, income: 0};
      const val = parseFloat(r.amount);
      if (r.record_type === 'cost') stats[r.category].cost += val;
      else stats[r.category].income += val;
    }
    return stats;
  }, [records, currentMonth]);

  const filteredRecords = useMemo(() => {
    let result = records.filter(r => r.record_date.startsWith(currentMonth));
    if (filter !== 'all') {
      result = result.filter(r => r.record_type === filter);
    }
    if (categoryFilter) {
      result = result.filter(r => r.category === categoryFilter);
    }
    return result;
  }, [records, currentMonth, filter, categoryFilter]);

  const handleCreate = () => {
    navigation.navigate('CostCreate');
  };

  const handleMonthChange = (event: DateTimePickerEvent, date?: Date) => {
    setShowDatePicker(Platform.OS === 'ios');
    if (date) {
      setSelectedMonth(date);
    }
  };

  const handleDelete = (record: CostRecord) => {
    Alert.alert('确认删除', `确定要删除这条记录吗？`, [
      {text: '取消', style: 'cancel'},
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteRecord(record.id, record.cycle_id || undefined);
          } catch (err) {
            // Error 已在 store 中处理
          }
        },
      },
    ]);
  };

  const renderFilter = () => (
    <View style={styles.filterRow}>
      {([
        {key: 'all', label: '全部'},
        {key: 'cost', label: '支出'},
        {key: 'income', label: '收入'},
      ] as {key: FilterType; label: string}[]).map(item => {
        const isActive = filter === item.key;
        return (
          <TouchableOpacity
            key={item.key}
            style={[
              styles.filterBtn,
              isActive && styles.filterBtnActive,
            ]}
            onPress={() => setFilter(item.key)}
            activeOpacity={0.7}>
            <Text
              style={[
                styles.filterText,
                isActive && styles.filterTextActive,
              ]}>
              {item.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  const renderCategoryFilter = () => (
    <View style={styles.categoryFilterRow}>
      <TouchableOpacity
        style={[
          styles.categoryChip,
          categoryFilter === null && styles.categoryChipActive,
        ]}
        onPress={() => setCategoryFilter(null)}>
        <Text
          style={[
            styles.categoryChipText,
            categoryFilter === null && styles.categoryChipTextActive,
          ]}>
          全部
        </Text>
      </TouchableOpacity>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {categoryList.map(cat => {
          const catStats = categoryStats[cat];
          const isActive = categoryFilter === cat;
          return (
            <TouchableOpacity
              key={cat}
              style={[
                styles.categoryChip,
                isActive && styles.categoryChipActive,
              ]}
              onPress={() => setCategoryFilter(cat)}>
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

  if (loading && records.length === 0) {
    return <Loading message="加载账单中..." />;
  }

  if (records.length === 0) {
    return (
      <View style={styles.container}>
        <View style={styles.statsSection}>
          <TouchableOpacity style={styles.monthSelector} onPress={() => setShowDatePicker(true)}>
            <Icon name="calendar-month" size={20} color={colors.primary} />
            <Text style={styles.monthText}>{dayjs(selectedMonth).format('YYYY年M月')}</Text>
            <Icon name="chevron-down" size={20} color={colors.primary} />
          </TouchableOpacity>
          <View style={styles.statsCards}>
            <Card style={[styles.statCard, styles.statCardCost]} padding="lg">
              <Text style={styles.statLabel}>支出</Text>
              <Text style={[styles.statValue, {color: colors.danger}]}>0.00</Text>
            </Card>
            <Card style={[styles.statCard, styles.statCardIncome]} padding="lg">
              <Text style={styles.statLabel}>收入</Text>
              <Text style={[styles.statValue, {color: colors.success}]}>0.00</Text>
            </Card>
            <Card style={[styles.statCard, styles.statCardBalance]} padding="lg">
              <Text style={styles.statLabel}>结余</Text>
              <Text style={[styles.statValue, {color: colors.text}]}>0.00</Text>
            </Card>
          </View>
          {showDatePicker && (
            <DateTimePicker
              value={selectedMonth}
              mode="date"
              display="compact"
              onChange={handleMonthChange}
              maximumDate={new Date()}
            />
          )}
        </View>
        <EmptyState
          title="暂无账单记录"
          subtitle="点击按钮记一笔"
          actionLabel="记一笔"
          onAction={handleCreate}
          icon="cash-remove"
        />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Stats Header */}
      <View style={styles.statsSection}>
        <TouchableOpacity style={styles.monthSelector} onPress={() => setShowDatePicker(true)}>
          <Icon name="calendar-month" size={20} color={colors.primary} />
          <Text style={styles.monthText}>{dayjs(selectedMonth).format('YYYY年M月')}</Text>
          <Icon name="chevron-down" size={20} color={colors.primary} />
        </TouchableOpacity>
        {showDatePicker && (
          <DateTimePicker
            value={selectedMonth}
            mode="date"
            display="compact"
            onChange={handleMonthChange}
            maximumDate={new Date()}
          />
        )}
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
            <Text style={[styles.statValue, {color: stats.balance >= 0 ? colors.success : colors.danger}]}>
              {stats.balance.toFixed(2)}
            </Text>
          </Card>
        </View>
      </View>

      {/* Category Filter */}
      {categoryList.length > 0 && renderCategoryFilter()}

      {/* Type Filter */}
      {renderFilter()}

      {/* List */}
      <FlatList
        data={filteredRecords}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        renderItem={({item}) => {
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
            <TouchableOpacity
              onLongPress={() => handleDelete(item)}
              delayLongPress={500}
              activeOpacity={0.7}>
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
                      {prefix}{item.amount}
                    </Text>
                    <View
                      style={[
                        styles.typeBadge,
                        {backgroundColor: config.bgColor},
                      ]}>
                      <Text style={[styles.typeText, {color: config.color}]}>
                        {config.label}
                      </Text>
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
        }}
      />
      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Icon name="plus" size={24} color={colors.textInverse} />
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
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
    gap: spacing.xs,
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
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  filterBtn: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  filterBtnActive: {
    backgroundColor: colors.primaryMuted,
    borderColor: colors.primary,
  },
  filterText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    fontWeight: '500',
  },
  filterTextActive: {
    color: colors.primary,
    fontWeight: '700',
  },
  listContent: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
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
  fab: {
    position: 'absolute',
    right: spacing.lg,
    bottom: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: colors.primary,
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 6,
  },
});
