import React, {useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  LayoutAnimation,
  Platform,
  UIManager,
} from 'react-native';
import {Card} from './Card';
import {Loading} from './Loading';
import {MarkdownText} from './MarkdownText';
import {colors} from '../theme/colors';
import {spacing, fontSize, borderRadius} from '../theme/spacing';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

if (Platform.OS === 'android') {
  UIManager.setLayoutAnimationEnabledExperimental?.(true);
}

interface AdviceCardProps {
  advice: string | null;
  loading?: boolean;
  onPress?: () => void;
}

const MAX_LINES = 4;

export const AdviceCard: React.FC<AdviceCardProps> = ({
  advice,
  loading = false,
  onPress,
}) => {
  const [expanded, setExpanded] = useState(false);

  const handleToggle = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded(!expanded);
  };

  return (
    <Card padding="lg" elevated={true}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.iconCircle}>
          <Icon name="sprout" size={20} color={colors.success} />
        </View>
        <View style={styles.headerText}>
          <Text style={styles.title}>今日农事建议</Text>
          <Text style={styles.subtitle}>AI 农事顾问</Text>
        </View>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>每日更新</Text>
        </View>
      </View>

      {/* Content */}
      {loading && (
        <View style={styles.center}>
          <Loading />
          <Text style={styles.hint}>AI 正在分析天气和作物数据...</Text>
        </View>
      )}

      {!loading && !advice && (
        <View style={styles.center}>
          <Icon
            name="information-outline"
            size={32}
            color={colors.textTertiary}
          />
          <Text style={styles.hint}>暂无建议，请稍后重试</Text>
        </View>
      )}

      {!loading && advice && (
        <>
          <View
            style={[
              styles.contentWrapper,
              !expanded && styles.contentCollapsed,
            ]}>
            <MarkdownText text={advice} />
          </View>

          {/* Expand / Collapse toggle */}
          {advice.split('\n').length > MAX_LINES && (
            <TouchableOpacity
              onPress={handleToggle}
              style={styles.toggleBtn}
              activeOpacity={0.7}>
              <Text style={styles.toggleText}>
                {expanded ? '收起' : '展开更多'}
              </Text>
              <Icon
                name={expanded ? 'chevron-up' : 'chevron-down'}
                size={16}
                color={colors.primary}
              />
            </TouchableOpacity>
          )}

          {/* Action bar */}
          <View style={styles.actionBar}>
            <TouchableOpacity
              style={styles.actionBtn}
              onPress={onPress}
              activeOpacity={0.7}>
              <Icon
                name="chat-processing-outline"
                size={18}
                color={colors.primary}
              />
              <Text style={styles.actionText}>继续咨询</Text>
            </TouchableOpacity>
          </View>
        </>
      )}
    </Card>
  );
};

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.successLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerText: {
    flex: 1,
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
  },
  subtitle: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
    marginTop: 2,
  },
  badge: {
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: borderRadius.sm,
  },
  badgeText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: '600',
  },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.xl,
    gap: spacing.sm,
  },
  hint: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
  },
  contentWrapper: {
    overflow: 'hidden',
  },
  contentCollapsed: {
    maxHeight: 140,
  },
  toggleBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.sm,
    paddingVertical: spacing.xs,
  },
  toggleText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
    marginRight: 2,
  },
  actionBar: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  actionBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  actionText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '600',
  },
});
