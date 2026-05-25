import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {useNavigation} from '@react-navigation/native';
import {useAgentStore} from '../../stores/agentStore';
import {useCycleStore} from '../../stores/cycleStore';
import {Card} from '../../components/Card';
import {WeatherCard} from '../../components/WeatherCard';
import {AdviceCard} from '../../components/AdviceCard';
import {CityPicker} from '../../components/CityPicker';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const getGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 11) return '早上好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  return '晚上好';
};

const QUICK_ACTIONS = [
  {
    label: '咨询顾问',
    icon: 'chat-processing',
    iconColor: '#0D7377',
    bgColor: 'rgba(13, 115, 119, 0.08)',
    route: 'AgentChat',
  },
  {
    label: '新建茬口',
    icon: 'plus-circle',
    iconColor: '#2D9E5F',
    bgColor: 'rgba(45, 158, 95, 0.08)',
    route: 'CycleCreate',
  },
  {
    label: '记一笔',
    icon: 'cash-register',
    iconColor: '#D4A843',
    bgColor: 'rgba(212, 168, 67, 0.08)',
    route: 'CostCreate',
  },
  {
    label: '分析报告',
    icon: 'file-chart',
    iconColor: '#3B82C4',
    bgColor: 'rgba(59, 130, 196, 0.08)',
    route: 'AgentReport',
  },
];

export const HomeScreen: React.FC = () => {
  const navigation = useNavigation();
  const {
    weather,
    dailyAdvice,
    fetchWeather,
    fetchDailyAdvice,
    refreshDailyAdvice,
    loading: agentLoading,
    cityName,
    setCity,
  } = useAgentStore();
  const {cycles, fetchCycles} = useCycleStore();
  const [pickerVisible, setPickerVisible] = useState(false);

  useEffect(() => {
    fetchWeather();
    fetchDailyAdvice();
    fetchCycles();
  }, [fetchWeather, fetchDailyAdvice, fetchCycles]);

  const recentCycles = cycles.slice(0, 3);
  const greeting = getGreeting();

  const handleAdvicePress = () => {
    (navigation as any).navigate('AgentChat');
  };

  const handleCitySelect = (city: {name: string; lat: number; lon: number}) => {
    setCity(city.name, city.lat, city.lon);
    fetchWeather();
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.headerSection}>
          <View style={styles.headerTop}>
            <View>
              <TouchableOpacity
                style={styles.cityRow}
                onPress={() => setPickerVisible(true)}
                activeOpacity={0.7}>
                <Icon name="map-marker" size={16} color={colors.primary} />
                <Text style={styles.cityName}>{cityName}</Text>
                <Icon
                  name="chevron-down"
                  size={16}
                  color={colors.primary}
                />
              </TouchableOpacity>
              <Text style={styles.greeting}>{greeting}，农友</Text>
              <Text style={styles.dateText}>
                {new Date().toLocaleDateString('zh-CN', {
                  month: 'long',
                  day: 'numeric',
                  weekday: 'long',
                })}
              </Text>
            </View>
            <View style={styles.avatar}>
              <Icon name="sprout" size={22} color={colors.primary} />
            </View>
          </View>
        </View>

        {/* Weather */}
        <View style={styles.section}>
          <WeatherCard data={weather} />
        </View>

        {/* Advice */}
        <View style={styles.section}>
          <AdviceCard
            advice={dailyAdvice?.advice || null}
            loading={agentLoading}
            onPress={handleAdvicePress}
            onRefresh={() => refreshDailyAdvice()}
          />
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>快捷操作</Text>
          <View style={styles.quickActionsGrid}>
            {QUICK_ACTIONS.map(action => (
              <TouchableOpacity
                key={action.label}
                style={styles.quickAction}
                onPress={() => navigation.navigate(action.route as never)}
                activeOpacity={0.7}>
                <View
                  style={[
                    styles.quickActionIcon,
                    {backgroundColor: action.bgColor},
                  ]}>
                  <Icon
                    name={action.icon}
                    size={22}
                    color={action.iconColor}
                  />
                </View>
                <Text style={styles.quickActionLabel}>{action.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Recent Cycles */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>最近茬口</Text>
            <TouchableOpacity
              onPress={() => navigation.navigate('Cycles' as never)}
              activeOpacity={0.7}>
              <Text style={styles.viewAll}>查看全部</Text>
            </TouchableOpacity>
          </View>

          {recentCycles.length === 0 && (
            <Card elevated={false} style={styles.emptyCard}>
              <View style={styles.emptyContent}>
                <Icon
                  name="sprout-outline"
                  size={32}
                  color={colors.textTertiary}
                />
                <Text style={styles.emptyText}>
                  暂无茬口，点击上方按钮创建
                </Text>
              </View>
            </Card>
          )}

          {recentCycles.map(cycle => (
            <TouchableOpacity
              key={cycle.id}
              style={styles.cycleCard}
              onPress={() =>
                (navigation as any).navigate('CycleDetail', {
                  cycleId: cycle.id,
                })
              }
              activeOpacity={0.7}>
              <Card style={styles.cycleInner}>
                <View style={styles.cycleRow}>
                  <View style={styles.cycleLeft}>
                    <View
                      style={[
                        styles.cycleIcon,
                        {backgroundColor: colors.successLight},
                      ]}>
                      <Icon name="seed" size={18} color={colors.success} />
                    </View>
                    <View style={styles.cycleInfo}>
                      <Text style={styles.cycleName}>{cycle.name}</Text>
                      <Text style={styles.cycleCrop}>
                        {cycle.crop_template_name}
                      </Text>
                    </View>
                  </View>
                  <Icon
                    name="chevron-right"
                    size={20}
                    color={colors.textTertiary}
                  />
                </View>
              </Card>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      <CityPicker
        visible={pickerVisible}
        selectedCity={cityName}
        onSelect={handleCitySelect}
        onClose={() => setPickerVisible(false)}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingBottom: spacing.xxl,
  },
  headerSection: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
  },
  headerTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cityRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: spacing.sm,
    alignSelf: 'flex-start',
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: borderRadius.md,
  },
  cityName: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.primary,
  },
  greeting: {
    fontSize: fontSize.xl,
    fontWeight: '800',
    color: colors.text,
  },
  dateText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 4,
  },
  avatar: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
  },
  viewAll: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
  },
  quickActionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.md,
  },
  quickAction: {
    width: '22.5%',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  quickActionIcon: {
    width: 44,
    height: 44,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  quickActionLabel: {
    fontSize: fontSize.xs,
    color: colors.text,
    fontWeight: '600',
  },
  cycleCard: {
    marginBottom: spacing.sm,
  },
  cycleInner: {
    padding: spacing.md,
  },
  cycleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cycleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  cycleIcon: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  cycleInfo: {
    flex: 1,
  },
  cycleName: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  cycleCrop: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  emptyCard: {
    padding: spacing.xl,
  },
  emptyContent: {
    alignItems: 'center',
    gap: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
