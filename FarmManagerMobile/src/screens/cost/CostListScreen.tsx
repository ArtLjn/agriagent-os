import React, {useEffect, useMemo, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import dayjs from 'dayjs';
import {useCostStore} from '../../stores/costStore';
import type {CostRecord} from '../../api/types';
import {EmptyState} from '../../components/EmptyState';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {MonthlyStats} from './components/MonthlyStats';
import {CategoryFilter} from './components/CategoryFilter';
import {RecordItem} from './components/RecordItem';
import {RecordDetailModal} from './components/RecordDetailModal';

type FilterType = 'all' | 'cost' | 'income';

type CostListNavigationProp = NativeStackNavigationProp<RootStackParamList, 'CostCreate'>;

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const {records, loading, fetchRecords, deleteRecord} = useCostStore();
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedMonth, setSelectedMonth] = useState(new Date());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedRecord, setSelectedRecord] = useState<CostRecord | null>(null);

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

  const handlePreviousMonth = () => {
    setSelectedMonth(dayjs(selectedMonth).subtract(1, 'month').toDate());
  };

  const handleNextMonth = () => {
    const nextMonth = dayjs(selectedMonth).add(1, 'month');
    // 不允许选择未来月份（严格大于当前月）
    if (!nextMonth.isAfter(dayjs(), 'month')) {
      setSelectedMonth(nextMonth.toDate());
    }
  };

  const handleShowDetail = (record: CostRecord) => {
    setSelectedRecord(record);
    setDetailVisible(true);
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
            style={[styles.filterBtn, isActive && styles.filterBtnActive]}
            onPress={() => setFilter(item.key)}
            activeOpacity={0.7}>
            <Text style={[styles.filterText, isActive && styles.filterTextActive]}>
              {item.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  if (loading && records.length === 0) {
    return <Loading message="加载账单中..." />;
  }

  if (records.length === 0) {
    return (
      <View style={styles.container}>
        <MonthlyStats
          selectedMonth={selectedMonth}
          stats={{cost: 0, income: 0, balance: 0}}
          onPreviousMonth={handlePreviousMonth}
          onNextMonth={handleNextMonth}
        />
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
      <MonthlyStats
        selectedMonth={selectedMonth}
        stats={stats}
        onPreviousMonth={handlePreviousMonth}
        onNextMonth={handleNextMonth}
      />

      {/* Category Filter */}
      {categoryList.length > 0 && (
        <CategoryFilter
          categoryList={categoryList}
          categoryStats={categoryStats}
          selectedCategory={categoryFilter}
          onSelectCategory={setCategoryFilter}
        />
      )}

      {/* Type Filter */}
      {renderFilter()}

      {/* List */}
      <FlatList
        data={filteredRecords}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={[
          styles.listContent,
          filteredRecords.length === 0 && styles.listEmpty,
        ]}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="clipboard-text-outline" size={48} color={colors.textTertiary} />
            <Text style={styles.emptyText}>本月暂无记录</Text>
            <Text style={styles.emptySubtext}>点击右下角按钮记一笔</Text>
          </View>
        }
        renderItem={({item}) => (
          <RecordItem
            item={item}
            onPress={() => handleShowDetail(item)}
            onLongPress={() => handleDelete(item)}
          />
        )}
      />
      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Icon name="plus" size={24} color={colors.textInverse} />
      </TouchableOpacity>

      <RecordDetailModal
        visible={detailVisible}
        record={selectedRecord}
        onClose={() => setDetailVisible(false)}
        onDelete={() => {
          setDetailVisible(false);
          if (selectedRecord) {
            handleDelete(selectedRecord);
          }
        }}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
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
  listEmpty: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    fontWeight: '600',
    marginTop: spacing.md,
  },
  emptySubtext: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    marginTop: spacing.xs,
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
