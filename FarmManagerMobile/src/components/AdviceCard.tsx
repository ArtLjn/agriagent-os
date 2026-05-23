import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Card } from './Card';
import { Loading } from './Loading';
import { colors } from '../theme/colors';
import { spacing, fontSize } from '../theme/spacing';

interface AdviceCardProps {
  advice: string | null;
  loading?: boolean;
}

export const AdviceCard: React.FC<AdviceCardProps> = ({ advice, loading = false }) => {
  return (
    <Card style={styles.card}>
      <Text style={styles.title}>今日农事建议</Text>

      {loading && (
        <View style={styles.center}>
          <Loading />
          <Text style={styles.hint}>正在获取建议...</Text>
        </View>
      )}

      {!loading && !advice && (
        <View style={styles.center}>
          <Text style={styles.hint}>暂无建议，请稍后重试</Text>
        </View>
      )}

      {!loading && advice && (
        <Text style={styles.content}>{advice}</Text>
      )}
    </Card>
  );
};

const styles = StyleSheet.create({
  card: {
    padding: spacing.md,
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  center: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.lg,
  },
  hint: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  content: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 24,
  },
});
