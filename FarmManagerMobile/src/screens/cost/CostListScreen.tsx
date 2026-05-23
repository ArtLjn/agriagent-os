import React, {useEffect} from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  TouchableOpacity,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {useCostStore} from '../../stores/costStore';
import {Card} from '../../components/Card';
import {EmptyState} from '../../components/EmptyState';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

const TYPE_LABELS: Record<string, string> = {
  cost: '支出',
  income: '收入',
};

const TYPE_COLORS: Record<string, string> = {
  cost: colors.danger,
  income: colors.success,
};

type CostListNavigationProp = NativeStackNavigationProp<
  RootStackParamList,
  'CostCreate'
>;

export const CostListScreen: React.FC = () => {
  const navigation = useNavigation<CostListNavigationProp>();
  const {records, loading, fetchRecords} = useCostStore();

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const handleCreate = () => {
    navigation.navigate('CostCreate');
  };

  if (loading && records.length === 0) {
    return <Loading message="加载账单中..." />;
  }

  if (records.length === 0) {
    return (
      <EmptyState
        title="暂无账单记录"
        subtitle="点击按钮记一笔"
        actionLabel="记一笔"
        onAction={handleCreate}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={records}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.listContent}
        renderItem={({item}) => {
          const isCost = item.record_type === 'cost';
          const prefix = isCost ? '-' : '+';
          const color = TYPE_COLORS[item.record_type] || colors.text;

          return (
            <Card style={styles.card}>
              <View style={styles.row}>
                <View style={styles.left}>
                  <Text style={styles.category}>{item.category}</Text>
                  <Text style={styles.date}>{item.record_date}</Text>
                </View>
                <View style={styles.right}>
                  <Text style={[styles.amount, {color}]}>
                    {prefix}{item.amount}
                  </Text>
                  <View
                    style={[
                      styles.typeBadge,
                      {backgroundColor: color + '20'},
                    ]}>
                    <Text style={[styles.typeText, {color}]}>
                      {TYPE_LABELS[item.record_type] || item.record_type}
                    </Text>
                  </View>
                </View>
              </View>
              {item.note ? (
                <Text style={styles.note} numberOfLines={1}>
                  {item.note}
                </Text>
              ) : null}
            </Card>
          );
        }}
      />
      <TouchableOpacity style={styles.fab} onPress={handleCreate}>
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  listContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  card: {
    marginBottom: spacing.md,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  left: {
    flex: 1,
  },
  right: {
    alignItems: 'flex-end',
  },
  category: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  date: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: spacing.xs,
  },
  amount: {
    fontSize: fontSize.xl,
    fontWeight: '700',
  },
  typeBadge: {
    marginTop: spacing.xs,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  typeText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  note: {
    marginTop: spacing.sm,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
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
    elevation: 4,
    shadowColor: colors.text,
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  fabText: {
    fontSize: fontSize.xxl,
    color: colors.textInverse,
    fontWeight: '600',
  },
});
