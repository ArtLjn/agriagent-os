import React, { useState } from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { MarkdownText } from '../../components/MarkdownText';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAgentStore } from '../../stores/agentStore';
import { Card } from '../../components/Card';
import { BigButton } from '../../components/BigButton';
import { Loading } from '../../components/Loading';
import { colors } from '../../theme/colors';
import { spacing, fontSize } from '../../theme/spacing';

type ReportType = 'weekly' | 'monthly';

export const AgentReportScreen: React.FC = () => {
  const [reportType, setReportType] = useState<ReportType>('weekly');
  const { report, generateReport, loading: isLoading } = useAgentStore();

  const handleGenerate = async () => {
    await generateReport(reportType);
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <Text style={styles.title}>农事报告</Text>

        <Card style={styles.toggleCard}>
          <View style={styles.toggleRow}>
            <BigButton
              title="周报"
              onPress={() => setReportType('weekly')}
              variant={reportType === 'weekly' ? 'primary' : 'secondary'}
              style={styles.toggleButton}
            />
            <BigButton
              title="月报"
              onPress={() => setReportType('monthly')}
              variant={reportType === 'monthly' ? 'primary' : 'secondary'}
              style={styles.toggleButton}
            />
          </View>
        </Card>

        <BigButton
          title="生成报告"
          onPress={handleGenerate}
          variant="primary"
          style={styles.generateButton}
        />

        {isLoading && (
          <View style={styles.loadingContainer}>
            <Loading />
            <Text style={styles.loadingText}>正在生成报告...</Text>
          </View>
        )}

        {!isLoading && report && (
          <Card style={styles.reportCard}>
            <Text style={styles.reportTitle}>
              {reportType === 'weekly' ? '本周农事报告' : '本月农事报告'}
            </Text>
            <MarkdownText text={report.content} baseStyle={styles.reportContent} />
          </Card>
        )}
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
    padding: spacing.md,
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.md,
  },
  toggleCard: {
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  toggleButton: {
    flex: 1,
    marginHorizontal: spacing.xs,
  },
  generateButton: {
    marginBottom: spacing.md,
  },
  loadingContainer: {
    alignItems: 'center',
    marginTop: spacing.lg,
  },
  loadingText: {
    marginTop: spacing.sm,
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  reportCard: {
    padding: spacing.md,
  },
  reportTitle: {
    fontSize: fontSize.lg,
    fontWeight: '700',
    color: colors.text,
    marginBottom: spacing.sm,
  },
  reportContent: {
    lineHeight: 24,
  },
});
