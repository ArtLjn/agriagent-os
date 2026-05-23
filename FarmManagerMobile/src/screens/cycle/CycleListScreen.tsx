import React, {useEffect} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {useCycleStore} from '../../stores/cycleStore';
import {Card} from '../../components/Card';
import {EmptyState} from '../../components/EmptyState';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const statusMap: Record<string, {label: string; color: string}> = {
  active: {label: '进行中', color: colors.success},
  completed: {label: '已完成', color: colors.info},
  abandoned: {label: '已废弃', color: colors.danger},
};

export const CycleListScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const {cycles, loading, fetchCycles} = useCycleStore();

  useEffect(() => {
    fetchCycles();
  }, [fetchCycles]);

  if (loading && cycles.length === 0) {
    return <Loading message="加载茬口列表..." />;
  }

  if (cycles.length === 0) {
    return (
      <EmptyState
        title="暂无茬口"
        subtitle="点击右下角按钮创建您的第一个种植茬口"
        actionLabel="新建茬口"
        onAction={() => navigation.navigate('CycleCreate')}
      />
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={cycles}
        keyExtractor={item => String(item.id)}
        contentContainerStyle={styles.list}
        renderItem={({item}) => {
          const status = statusMap[item.status] || {
            label: item.status,
            color: colors.textSecondary,
          };
          return (
            <TouchableOpacity
              onPress={() =>
                navigation.navigate('CycleDetail', {cycleId: item.id})
              }>
              <Card style={styles.card}>
                <View style={styles.header}>
                  <Text style={styles.name}>{item.name}</Text>
                  <View
                    style={[
                      styles.badge,
                      {backgroundColor: status.color + '20'},
                    ]}>
                    <Text style={[styles.badgeText, {color: status.color}]}>
                      {status.label}
                    </Text>
                  </View>
                </View>
                <Text style={styles.template}>
                  作物模板：{item.crop_template_name}
                </Text>
                <Text style={styles.meta}>
                  起始日期：{item.start_date}
                </Text>
                {item.current_stage_name && (
                  <Text style={styles.stage}>
                    当前阶段：{item.current_stage_name}
                  </Text>
                )}
              </Card>
            </TouchableOpacity>
          );
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
  list: {
    padding: spacing.md,
  },
  card: {
    marginBottom: spacing.md,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  name: {
    fontSize: fontSize.lg,
    fontWeight: '600',
    color: colors.text,
    flex: 1,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: 4,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: '600',
  },
  template: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  meta: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  stage: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '500',
  },
});
