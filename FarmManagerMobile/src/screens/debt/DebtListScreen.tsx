import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  Alert,
  RefreshControl,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import {useDebtStore} from '../../stores/debtStore';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';

// 临时类型定义，等待导航类型更新
 type DebtListNavigationProp = NativeStackNavigationProp<any, 'DebtList'>;

export const DebtListScreen: React.FC = () => {
  const navigation = useNavigation<DebtListNavigationProp>();
  const {debts, summary, loading, error, fetchDebts, settleDebt, clearError} = useDebtStore();
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchDebts();
  }, []);

  useEffect(() => {
    if (error) {
      Alert.alert('错误', error);
      clearError();
    }
  }, [error]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDebts();
    setRefreshing(false);
  };

  const handleSettle = (counterparty: string) => {
    Alert.alert(
      '确认还款',
      `确认结清 ${counterparty} 的欠款？`,
      [
        {text: '取消', style: 'cancel'},
        {
          text: '确认',
          onPress: () => settleDebt(counterparty),
        },
      ],
    );
  };

  const renderSummary = () => (
    <View style={styles.summaryContainer}>
      <Text style={styles.summaryTitle}>债务概览</Text>
      {summary.map(s => (
        <View key={s.counterparty} style={styles.summaryItem}>
          <Text style={styles.summaryName}>{s.counterparty}</Text>
          <Text style={styles.summaryAmount}>
            欠 {s.total_debt}元 / 已还 {s.total_settled}元 / 剩 {s.remaining}元
          </Text>
        </View>
      ))}
      {summary.length === 0 && (
        <Text style={styles.emptyText}>暂无赊账记录</Text>
      )}
    </View>
  );

  const renderDebtItem = ({item}: {item: any}) => (
    <View style={styles.debtCard}>
      <View style={styles.debtHeader}>
        <Text style={styles.debtCategory}>{item.category}</Text>
        <Text style={styles.debtAmount}>{item.amount}元</Text>
      </View>
      <Text style={styles.debtCounterparty}>债权人：{item.counterparty || '未指定'}</Text>
      <Text style={styles.debtDate}>日期：{item.record_date}</Text>
      {item.due_date && (
        <Text style={styles.debtDueDate}>到期：{item.due_date}</Text>
      )}
      {item.note && <Text style={styles.debtNote}>备注：{item.note}</Text>}
      <TouchableOpacity
        style={styles.settleButton}
        onPress={() => handleSettle(item.counterparty)}>
        <Text style={styles.settleButtonText}>还款</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>赊账管理</Text>
        <TouchableOpacity
          style={styles.addButton}
          onPress={() => navigation.navigate('DebtCreate')}>
          <Icon name="plus" size={24} color={colors.primary} />
        </TouchableOpacity>
      </View>

      <FlatList
        data={debts}
        keyExtractor={item => String(item.id)}
        ListHeaderComponent={renderSummary}
        renderItem={renderDebtItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          !loading ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>暂无未结清赊账</Text>
            </View>
          ) : null
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  headerTitle: {fontSize: fontSize.xl, fontWeight: '700', color: colors.text},
  addButton: {padding: spacing.sm},
  listContent: {padding: spacing.md},
  summaryContainer: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  summaryTitle: {fontSize: fontSize.lg, fontWeight: '600', marginBottom: spacing.sm, color: colors.text},
  summaryItem: {marginBottom: spacing.xs},
  summaryName: {fontSize: fontSize.md, fontWeight: '500', color: colors.text},
  summaryAmount: {fontSize: fontSize.sm, color: colors.textSecondary},
  debtCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  debtHeader: {flexDirection: 'row', justifyContent: 'space-between', marginBottom: spacing.xs},
  debtCategory: {fontSize: fontSize.md, fontWeight: '600', color: colors.text},
  debtAmount: {fontSize: fontSize.md, fontWeight: '700', color: colors.danger},
  debtCounterparty: {fontSize: fontSize.sm, color: colors.text},
  debtDate: {fontSize: fontSize.sm, color: colors.textSecondary},
  debtDueDate: {fontSize: fontSize.sm, color: colors.warning},
  debtNote: {fontSize: fontSize.sm, color: colors.textSecondary, marginTop: spacing.xs},
  settleButton: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.sm,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  settleButtonText: {color: colors.textInverse, fontWeight: '600'},
  emptyContainer: {alignItems: 'center', paddingVertical: spacing.xl},
  emptyText: {color: colors.textSecondary, fontSize: fontSize.md},
});
