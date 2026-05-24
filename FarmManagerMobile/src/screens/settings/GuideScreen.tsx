import React from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
} from 'react-native';
import {SafeAreaView} from 'react-native-safe-area-context';
import {Card} from '../../components/Card';
import {colors} from '../../theme/colors';
import {spacing, fontSize, borderRadius} from '../../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

interface GuideItem {
  title: string;
  icon: string;
  iconColor: string;
  bgColor: string;
  steps: string[];
}

const GUIDES: GuideItem[] = [
  {
    title: '创建种植茬口',
    icon: 'sprout',
    iconColor: colors.success,
    bgColor: colors.successLight,
    steps: [
      '在首页点击「新建茬口」快捷按钮',
      '选择作物类型，如水稻、小麦等',
      '填写茬口名称和起始日期',
      '保存后即可在首页看到新茬口',
    ],
  },
  {
    title: '记录农事活动',
    icon: 'clipboard-check',
    iconColor: colors.primary,
    bgColor: colors.primaryMuted,
    steps: [
      '进入某个茬口的详情页面',
      '点击「农事记录」查看已有记录',
      '点击右下角按钮添加新的农事活动',
      '选择操作类型和日期，添加备注',
    ],
  },
  {
    title: '记账管理',
    icon: 'cash-register',
    iconColor: colors.accent,
    bgColor: colors.accentMuted,
    steps: [
      '在底部导航栏点击「记账」',
      '点击右下角「+」按钮记一笔',
      '选择支出或收入类型',
      '填写金额、分类和日期后保存',
      '在茬口详情中可查看利润统计',
    ],
  },
  {
    title: 'AI 农事顾问',
    icon: 'chat-processing',
    iconColor: colors.info,
    bgColor: colors.infoLight,
    steps: [
      '在底部导航栏点击「AI助手」',
      '点击「农事顾问」开始对话',
      '可以咨询种植、病虫害、天气等问题',
      '也可以生成周报、月报分析种植情况',
    ],
  },
  {
    title: '天气与建议',
    icon: 'weather-partly-cloudy',
    iconColor: colors.warning,
    bgColor: colors.warningLight,
    steps: [
      '首页顶部显示当前城市的天气',
      '点击左上角城市名可切换城市',
      '每日农事建议会根据天气自动生成',
      '点击建议卡片可继续与 AI 深入交流',
    ],
  },
];

export const GuideScreen: React.FC = () => {
  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}>
        <Text style={styles.pageTitle}>使用指南</Text>
        <Text style={styles.pageSubtitle}>快速上手，轻松管理种植事务</Text>

        {GUIDES.map((guide, index) => (
          <Card key={guide.title} style={styles.guideCard}>
            <View style={styles.guideHeader}>
              <View
                style={[styles.guideIcon, {backgroundColor: guide.bgColor}]}>
                <Icon name={guide.icon} size={22} color={guide.iconColor} />
              </View>
              <Text style={styles.guideTitle}>{guide.title}</Text>
            </View>
            <View style={styles.stepsContainer}>
              {guide.steps.map((step, stepIndex) => (
                <View key={stepIndex} style={styles.stepRow}>
                  <View style={styles.stepNumber}>
                    <Text style={styles.stepNumberText}>{stepIndex + 1}</Text>
                  </View>
                  <Text style={styles.stepText}>{step}</Text>
                </View>
              ))}
            </View>
          </Card>
        ))}
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
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  pageTitle: {
    fontSize: fontSize.xl,
    fontWeight: '800',
    color: colors.text,
    marginBottom: spacing.xs,
  },
  pageSubtitle: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginBottom: spacing.lg,
  },
  guideCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  guideHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  guideIcon: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  guideTitle: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  stepsContainer: {
    gap: spacing.sm,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  stepNumber: {
    width: 22,
    height: 22,
    borderRadius: borderRadius.full,
    backgroundColor: colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
    marginTop: 1,
  },
  stepNumberText: {
    fontSize: fontSize.xs,
    fontWeight: '700',
    color: colors.primary,
  },
  stepText: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 22,
  },
});
