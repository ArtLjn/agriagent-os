import React, {useEffect} from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {useNavigation} from '@react-navigation/native';
import type {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {useAgentStore} from '../../stores/agentStore';
import {Card} from '../../components/Card';
import {MarkdownText} from '../../components/MarkdownText';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import type {RootStackParamList} from '../../navigation/AppNavigator';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

type NavigationProp = NativeStackNavigationProp<RootStackParamList>;

const FEATURES = [
  {
    title: '农事顾问',
    subtitle: '随时解答种植问题',
    icon: 'chat-processing',
    iconColor: colors.primary,
    bgColor: colors.primaryMuted,
    route: 'AgentChat' as const,
  },
  {
    title: '种植报告',
    subtitle: '生成周报与月报',
    icon: 'file-document',
    iconColor: colors.success,
    bgColor: colors.successLight,
    route: 'AgentReport' as const,
  },
];

export const AgentTabScreen: React.FC = () => {
  const navigation = useNavigation<NavigationProp>();
  const {dailyAdvice, fetchDailyAdvice, loading} = useAgentStore();

  useEffect(() => {
    fetchDailyAdvice();
  }, [fetchDailyAdvice]);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}>
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.headerAvatar}>
            <Icon name="robot-happy" size={36} color={colors.primary} />
          </View>
          <Text style={styles.headerTitle}>AI 农事助手</Text>
          <Text style={styles.headerSubtitle}>
            智能分析 · 专业建议 · 实时解答
          </Text>
        </View>

        {/* Features */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>快捷功能</Text>
          <View style={styles.featuresRow}>
            {FEATURES.map(feature => (
              <TouchableOpacity
                key={feature.title}
                style={styles.featureCard}
                onPress={() => navigation.navigate(feature.route as never)}
                activeOpacity={0.7}>
                <View
                  style={[
                    styles.featureIcon,
                    {backgroundColor: feature.bgColor},
                  ]}>
                  <Icon
                    name={feature.icon}
                    size={28}
                    color={feature.iconColor}
                  />
                </View>
                <Text style={styles.featureTitle}>{feature.title}</Text>
                <Text style={styles.featureSubtitle}>{feature.subtitle}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Daily Advice */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>今日建议</Text>
          <TouchableOpacity
            activeOpacity={0.7}
            onPress={() => navigation.navigate('AgentChat' as never)}>
            <Card style={styles.adviceCard}>
              {loading || !dailyAdvice ? (
                <View style={styles.adviceLoading}>
                  <Icon
                    name="loading"
                    size={20}
                    color={colors.textTertiary}
                  />
                  <Text style={styles.adviceLoadingText}>加载中...</Text>
                </View>
              ) : (
                <>
                  <MarkdownText
                    text={dailyAdvice.advice}
                    baseStyle={styles.adviceText}
                  />
                  <View style={styles.adviceFooter}>
                    <Text style={styles.adviceHint}>点击继续咨询</Text>
                    <Icon
                      name="chevron-right"
                      size={16}
                      color={colors.primary}
                    />
                  </View>
                </>
              )}
            </Card>
          </TouchableOpacity>
        </View>
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
    paddingBottom: spacing.xxl,
  },
  header: {
    alignItems: 'center',
    paddingVertical: spacing.xl,
    paddingHorizontal: spacing.lg,
  },
  headerAvatar: {
    width: 72,
    height: 72,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: '800',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  headerSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  section: {
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.lg,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.md,
  },
  featuresRow: {
    flexDirection: 'row',
    gap: spacing.md,
  },
  featureCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  featureIcon: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  featureTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
    marginBottom: 2,
  },
  featureSubtitle: {
    fontSize: fontSize.xs,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  adviceCard: {
    padding: spacing.md,
  },
  adviceText: {
    fontSize: fontSize.sm,
    color: colors.text,
    lineHeight: 22,
  },
  adviceFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
    gap: spacing.xs,
  },
  adviceHint: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
  },
  adviceLoading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.lg,
  },
  adviceLoadingText: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
});
