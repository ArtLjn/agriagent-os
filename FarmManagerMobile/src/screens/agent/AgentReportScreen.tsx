import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
} from "react-native";
import { MarkdownText } from "../../components/MarkdownText";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRoute } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { Loading } from "../../components/Loading";
import { colors } from "../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

type ReportType = "weekly" | "monthly";

export const AgentReportScreen: React.FC = () => {
  const route = useRoute<any>();
  const [reportType, setReportType] = useState<ReportType>("weekly");
  const { report, generateReport, loading: isLoading } = useAgentStore();

  const passedContent = route.params?.content as string | undefined;
  const passedReportType = route.params?.reportType as string | undefined;
  const passedCreatedAt = route.params?.createdAt as string | undefined;
  const isViewMode = !!passedContent;

  const handleGenerate = async () => {
    await generateReport(reportType);
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {isViewMode ? (
          <>
            <View style={styles.viewHeader}>
              <View style={styles.viewHeaderBadge}>
                <Icon
                  name={
                    passedReportType === "weekly"
                      ? "calendar-week"
                      : "calendar-month"
                  }
                  size={14}
                  color={colors.primary}
                />
                <Text style={styles.viewHeaderTitle}>
                  {passedReportType === "weekly"
                    ? "周报"
                    : passedReportType === "monthly"
                    ? "月报"
                    : "农事报告"}
                </Text>
              </View>
              {passedCreatedAt && (
                <Text style={styles.viewHeaderDate}>
                  {new Date(passedCreatedAt).toLocaleDateString("zh-CN", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </Text>
              )}
            </View>
            <View style={styles.reportCard}>
              <MarkdownText text={passedContent!} />
            </View>
          </>
        ) : (
          <>
            {/* 页面头部 */}
            <View style={styles.pageHeader}>
              <View style={styles.pageHeaderIcon}>
                <Icon
                  name="file-document-edit"
                  size={28}
                  color={colors.primary}
                />
              </View>
              <View>
                <Text style={styles.pageHeaderTitle}>农事报告</Text>
                <Text style={styles.pageHeaderSub}>
                  基于种植数据自动生成周报/月报
                </Text>
              </View>
            </View>

            {/* 报告类型选择 */}
            <Text style={styles.sectionLabel}>报告类型</Text>
            <View style={styles.toggleRow}>
              <TouchableOpacity
                style={[
                  styles.typePill,
                  reportType === "weekly" && styles.typePillActive,
                ]}
                onPress={() => setReportType("weekly")}
                activeOpacity={0.7}
              >
                <Icon
                  name="calendar-week"
                  size={18}
                  color={
                    reportType === "weekly" ? "#FFFFFF" : colors.textSecondary
                  }
                />
                <Text
                  style={[
                    styles.typePillText,
                    reportType === "weekly" && styles.typePillTextActive,
                  ]}
                >
                  周报
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.typePill,
                  reportType === "monthly" && styles.typePillActive,
                ]}
                onPress={() => setReportType("monthly")}
                activeOpacity={0.7}
              >
                <Icon
                  name="calendar-month"
                  size={18}
                  color={
                    reportType === "monthly" ? "#FFFFFF" : colors.textSecondary
                  }
                />
                <Text
                  style={[
                    styles.typePillText,
                    reportType === "monthly" && styles.typePillTextActive,
                  ]}
                >
                  月报
                </Text>
              </TouchableOpacity>
            </View>

            {/* 生成按钮 */}
            <TouchableOpacity
              style={styles.generateBtn}
              onPress={handleGenerate}
              activeOpacity={0.7}
              disabled={isLoading}
            >
              <Icon name="auto-fix" size={22} color="#FFFFFF" />
              <Text style={styles.generateBtnText}>生成报告</Text>
            </TouchableOpacity>

            {isLoading && (
              <View style={styles.loadingContainer}>
                <Loading />
                <Text style={styles.loadingText}>
                  正在分析数据并生成报告...
                </Text>
              </View>
            )}

            {!isLoading && report && (
              <>
                <View style={styles.resultHeader}>
                  <Icon name="check-circle" size={18} color={colors.success} />
                  <Text style={styles.resultHeaderText}>
                    {reportType === "weekly" ? "本周农事报告" : "本月农事报告"}
                  </Text>
                </View>
                <View style={styles.reportCard}>
                  <MarkdownText text={report.content} />
                </View>
              </>
            )}
          </>
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
    flexGrow: 1,
  },
  viewHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.lg,
    paddingHorizontal: spacing.xs,
  },
  viewHeaderBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  viewHeaderTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.primary,
  },
  viewHeaderDate: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  pageHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  pageHeaderIcon: {
    width: 48,
    height: 48,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.primaryMuted,
    alignItems: "center",
    justifyContent: "center",
  },
  pageHeaderTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.text,
  },
  pageHeaderSub: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  sectionLabel: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.textSecondary,
    marginBottom: spacing.sm,
    letterSpacing: 0.5,
  },
  toggleRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  typePill: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.borderLight,
  },
  typePillActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  typePillText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  typePillTextActive: {
    color: "#FFFFFF",
    fontWeight: "700",
  },
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  generateBtnText: {
    color: "#FFFFFF",
    fontSize: fontSize.md,
    fontWeight: "700",
  },
  loadingContainer: {
    alignItems: "center",
    marginTop: spacing.lg,
  },
  loadingText: {
    marginTop: spacing.sm,
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  resultHeaderText: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.success,
  },
  reportCard: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.xl,
    padding: spacing.lg,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
});
