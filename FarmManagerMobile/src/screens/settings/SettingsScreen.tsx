import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { Card } from '../../components/Card';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

export const SettingsScreen: React.FC = () => {
  const navigation = useNavigation();

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>我的</Text>
      </View>

      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>AI功能</Text>
        <TouchableOpacity
          style={styles.linkRow}
          onPress={() => navigation.navigate('AgentChat' as never)}
        >
          <Text style={styles.linkText}>农事顾问</Text>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
        <View style={styles.divider} />
        <TouchableOpacity
          style={styles.linkRow}
          onPress={() => navigation.navigate('AgentReport' as never)}
        >
          <Text style={styles.linkText}>农事报告</Text>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
      </Card>

      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>关于</Text>
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>版本</Text>
          <Text style={styles.infoValue}>农事助手 v1.0</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>描述</Text>
          <Text style={styles.infoValue}>为父母辈农民设计的种植管理工具</Text>
        </View>
      </Card>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
  },
  sectionCard: {
    marginHorizontal: spacing.md,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  sectionTitle: {
    fontSize: fontSize.sm,
    fontWeight: '600',
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
  },
  linkText: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  chevron: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
  },
  infoLabel: {
    fontSize: fontSize.md,
    color: colors.text,
  },
  infoValue: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
});
