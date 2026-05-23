import React, { useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAgentStore } from '../../stores/agentStore';
import { useCycleStore } from '../../stores/cycleStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { WeatherCard } from '../../components/WeatherCard';
import { AdviceCard } from '../../components/AdviceCard';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation();
  const { weather, dailyAdvice, fetchWeather, fetchDailyAdvice, isLoading } = useAgentStore();
  const { cycles, fetchCycles } = useCycleStore();

  useEffect(() => {
    fetchWeather();
    fetchDailyAdvice();
    fetchCycles();
  }, [fetchWeather, fetchDailyAdvice, fetchCycles]);

  const recentCycles = cycles.slice(0, 3);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.greeting}>农事助手</Text>

        {weather && <WeatherCard weather={weather} />}

        <AdviceCard advice={dailyAdvice} loading={isLoading} />

        <Card style={styles.quickActionsCard}>
          <Text style={styles.sectionTitle}>快捷操作</Text>
          <View style={styles.quickActionsRow}>
            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => navigation.navigate('AgentChat' as never)}
            >
              <View style={[styles.quickActionIcon, { backgroundColor: colors.primaryLight }]}>
                <Text style={styles.quickActionEmoji}>💬</Text>
              </View>
              <Text style={styles.quickActionLabel}>咨询农事顾问</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => navigation.navigate('CreateCycle' as never)}
            >
              <View style={[styles.quickActionIcon, { backgroundColor: colors.successLight }]}>
                <Text style={styles.quickActionEmoji}>➕</Text>
              </View>
              <Text style={styles.quickActionLabel}>新建茬口</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.quickAction}
              onPress={() => navigation.navigate('RecordTransaction' as never)}
            >
              <View style={[styles.quickActionIcon, { backgroundColor: colors.warningLight }]}>
                <Text style={styles.quickActionEmoji}>📝</Text>
              </View>
              <Text style={styles.quickActionLabel}>记一笔</Text>
            </TouchableOpacity>
          </View>
        </Card>

        <Card style={styles.cyclesCard}>
          <View style={styles.cyclesHeader}>
            <Text style={styles.sectionTitle}>最近茬口</Text>
            <TouchableOpacity onPress={() => navigation.navigate('Cycles' as never)}>
              <Text style={styles.viewAll}>查看全部 ›</Text>
            </TouchableOpacity>
          </View>

          {recentCycles.length === 0 && (
            <Text style={styles.emptyText}>暂无茬口，点击上方按钮创建</Text>
          )}

          {recentCycles.map((cycle) => (
            <TouchableOpacity
              key={cycle.id}
              style={styles.cycleRow}
              onPress={() => navigation.navigate('CycleDetail', { cycleId: cycle.id } as never)}
            >
              <View>
                <Text style={styles.cycleName}>{cycle.name}</Text>
                <Text style={styles.cycleCrop}>{cycle.cropName}</Text>
              </View>
              <Text style={styles.chevron}>›</Text>
            </TouchableOpacity>
          ))}
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacing.lg,
  },
  greeting: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  quickActionsCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  quickActionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  quickAction: {
    alignItems: 'center',
    flex: 1,
  },
  quickActionIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.xs,
  },
  quickActionEmoji: {
    fontSize: 24,
  },
  quickActionLabel: {
    fontSize: fontSize.sm,
    color: colors.text,
    textAlign: 'center',
  },
  cyclesCard: {
    marginHorizontal: spacing.md,
    padding: spacing.md,
  },
  cyclesHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  viewAll: {
    fontSize: fontSize.sm,
    color: colors.primary,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingVertical: spacing.lg,
  },
  cycleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  cycleName: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
  },
  cycleCrop: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  chevron: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
  },
});
