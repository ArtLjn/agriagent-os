import React, {useEffect} from 'react';
import {View, Text, StyleSheet, ScrollView} from 'react-native';
import {useNavigation, useRoute, type RouteProp} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import {useCycleStore} from '../../stores/cycleStore';
import {Timeline} from '../../components/Timeline';
import {BigButton} from '../../components/BigButton';
import {Loading} from '../../components/Loading';
import {colors} from '../../theme/colors';
import {spacing, fontSize} from '../../theme/spacing';

type RouteParams = RouteProp<RootStackParamList, 'CycleDetail'>;
type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

export const CycleDetailScreen: React.FC = () => {
  const route = useRoute<RouteParams>();
  const navigation = useNavigation<NavigationProp>();
  const {cycleId} = route.params;
  const {currentCycle, loading, fetchCycleDetail} = useCycleStore();

  useEffect(() => {
    fetchCycleDetail(cycleId);
  }, [cycleId]);

  if (loading || !currentCycle) {
    return <Loading />;
  }

  const timelineItems = currentCycle.stages.map(stage => ({
    id: stage.id,
    title: stage.name,
    subtitle: stage.key_tasks || '无关键任务',
    dateRange: `${stage.start_date} ~ ${stage.end_date}`,
    isCurrent: stage.is_current,
  }));

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <Text style={styles.title}>{currentCycle.name}</Text>
        <Text style={styles.subtitle}>地块：{currentCycle.field_name || '未指定'}</Text>
        <Text style={styles.subtitle}>状态：{currentCycle.status}</Text>
        <Text style={styles.subtitle}>开始日期：{currentCycle.start_date}</Text>
      </View>

      <Text style={styles.sectionTitle}>生长阶段</Text>
      <Timeline items={timelineItems} />

      <View style={styles.actions}>
        <BigButton title="农事记录" onPress={() => navigation.navigate('LogList', {cycleId})} />
        <BigButton title="利润统计" variant="secondary" onPress={() => navigation.navigate('Profit', {cycleId})} />
        <BigButton title="问农事顾问" variant="secondary" onPress={() => navigation.navigate('AgentChat', {cycleId})} />
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: spacing.md, paddingBottom: spacing.xxl},
  header: {marginBottom: spacing.lg},
  title: {fontSize: fontSize.xxl, fontWeight: '700', color: colors.primary, marginBottom: spacing.sm},
  subtitle: {fontSize: fontSize.md, color: colors.textSecondary, marginBottom: spacing.xs},
  sectionTitle: {fontSize: fontSize.xl, fontWeight: '600', color: colors.text, marginBottom: spacing.md},
  actions: {gap: spacing.md, marginTop: spacing.lg},
});
