import React, { useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRoute } from "@react-navigation/native";
import { useAgentStore } from "../../stores/agentStore";
import { Loading } from "../../components/Loading";
import { MarkdownText } from "../../components/MarkdownText";
import { ReportHeader } from "../../components/report/ReportHeader";
import { ReportOverviewRow } from "../../components/report/ReportOverviewRow";
import { CropProgressCard } from "../../components/report/CropProgressCard";
import { CostBreakdownCard } from "../../components/report/CostBreakdownCard";
import { FarmLogListCard } from "../../components/report/FarmLogListCard";
import { AdviceCard } from "../../components/report/AdviceCard";
import { Section } from "../../components/report/Section";
import { FadeInListItem } from "../../components/animations/FadeInListItem";
import { ScalePress } from "../../components/animations/ScalePress";
import { colors } from "../../theme/colors";
import { farmTheme } from "../../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import type { StructuredReportData } from "../../api/types";

type ReportType = "weekly" | "monthly";

const ReportContent: React.FC<{
  data: StructuredReportData;
  createdAt?: string;
}> = ({ data, createdAt }) => {
  const sectionStartIndex = data.summary ? 3 : 2;

  return (
    <>
      <FadeInListItem index={0}>
        <ReportHeader
          reportType={data.report_type}
          periodStart={data.period_start}
          periodEnd={data.period_end}
          createdAt={createdAt || new Date().toISOString()}
        />
      </FadeInListItem>
      {data.summary ? (
        <FadeInListItem index={1}>
          <View style={styles.summaryCard}>
            <View style={styles.summaryIcon}>
              <Icon
                name="text-box-check-outline"
                size={20}
                color={farmTheme.colors.leaf}
              />
            </View>
            <View style={styles.summaryCopy}>
              <Text style={styles.summaryLabel}>报告摘要</Text>
              <Text style={styles.summaryText}>{data.summary}</Text>
            </View>
          </View>
        </FadeInListItem>
      ) : null}
      <FadeInListItem index={data.summary ? 2 : 1}>
        <ReportOverviewRow metrics={data.overview} />
      </FadeInListItem>

      {data.cycles.length > 0 && (
        <FadeInListItem index={sectionStartIndex}>
          <Section title="茬口进度">
            {data.cycles.map((c) => (
              <CropProgressCard key={c.cycle_id} data={c} />
            ))}
          </Section>
        </FadeInListItem>
      )}

      {data.costs.length > 0 && (
        <FadeInListItem index={sectionStartIndex + 1}>
          <Section title="收支明细">
            <CostBreakdownCard costs={data.costs} />
          </Section>
        </FadeInListItem>
      )}

      {data.logs.length > 0 && (
        <FadeInListItem index={sectionStartIndex + 2}>
          <Section title="农事记录">
            <FarmLogListCard logs={data.logs} />
          </Section>
        </FadeInListItem>
      )}

      <FadeInListItem index={sectionStartIndex + 3}>
        <Section title="农事建议">
          <AdviceCard items={data.advice} />
        </Section>
      </FadeInListItem>
    </>
  );
};

export const AgentReportScreen: React.FC = () => {
  const route = useRoute<any>();
  const [reportType, setReportType] = useState<ReportType>("weekly");
  const { report, generateReport, loading: isLoading } = useAgentStore();

  // 路由参数：从报告历史页面传入
  const passedStructuredData = route.params?.structuredData as
    | StructuredReportData
    | undefined;
  const passedContent = route.params?.content as string | undefined;
  const passedReportType = route.params?.reportType as string | undefined;
  const passedCreatedAt = route.params?.createdAt as string | undefined;
  const isViewMode = !!(passedStructuredData || passedContent);
  const currentReportLabel =
    reportType === "weekly" ? "本周农事报告" : "本月农事报告";

  const handleGenerate = async () => {
    await generateReport(reportType);
  };

  return (
    <SafeAreaView style={styles.container} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {isViewMode ? (
          <>
            {/* 查看模式：优先用结构化数据，否则降级到 Markdown */}
            {passedStructuredData ? (
              <ReportContent
                data={passedStructuredData}
                createdAt={passedCreatedAt}
              />
            ) : (
              <>
                <FadeInListItem index={0}>
                  <View style={styles.viewHero}>
                    <View style={styles.viewHeroGlow} />
                    <View style={styles.viewHeroTop}>
                      <View style={styles.viewHeaderBadge}>
                        <Icon
                          name={
                            passedReportType === "weekly"
                              ? "calendar-week"
                              : "calendar-month"
                          }
                          size={15}
                          color="#FFFFFF"
                        />
                        <Text style={styles.viewHeaderTitle}>
                          {passedReportType === "weekly"
                            ? "周报"
                            : passedReportType === "monthly"
                            ? "月报"
                            : "农事报告"}
                        </Text>
                      </View>
                      <Icon
                        name="file-chart-outline"
                        size={30}
                        color="#FFFFFF"
                      />
                    </View>
                    <Text style={styles.viewHeroTitle}>农事复盘已生成</Text>
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
                </FadeInListItem>
                <FadeInListItem index={1}>
                  <View style={styles.reportCard}>
                    <MarkdownText text={passedContent!} />
                  </View>
                </FadeInListItem>
              </>
            )}
          </>
        ) : (
          <>
            {/* 页面头部 */}
            <View style={styles.pageHero}>
              <View style={styles.pageHeroGlow} />
              <View style={styles.pageHeroTop}>
                <View style={styles.pageHeaderIcon}>
                  <Icon name="file-document-edit" size={28} color="#FFFFFF" />
                </View>
                <View style={styles.pageHeroBadge}>
                  <Icon name="sparkles" size={14} color="#D8F0BC" />
                  <Text style={styles.pageHeroBadgeText}>芽芽自动整理</Text>
                </View>
              </View>
              <Text style={styles.pageHeaderTitle}>生成农事报告</Text>
              <Text style={styles.pageHeaderSub}>
                把种植进度、农事记录、成本收支和建议整理成一份可回看的复盘。
              </Text>
            </View>

            {/* 报告类型选择 */}
            <Text style={styles.sectionLabel}>选择报告类型</Text>
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
                    reportType === "weekly"
                      ? farmTheme.colors.leaf
                      : colors.textSecondary
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
                    reportType === "monthly"
                      ? farmTheme.colors.leaf
                      : colors.textSecondary
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
            <ScalePress onPress={handleGenerate} disabled={isLoading}>
              <View
                style={[
                  styles.generateBtn,
                  isLoading && styles.generateBtnDisabled,
                ]}
              >
                <Icon name="auto-fix" size={22} color="#FFFFFF" />
                <Text style={styles.generateBtnText}>
                  生成{currentReportLabel}
                </Text>
              </View>
            </ScalePress>

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
                {report.structured_data ? (
                  <ReportContent
                    data={report.structured_data}
                    createdAt={report.created_at}
                  />
                ) : (
                  <>
                    <FadeInListItem index={0}>
                      <View style={styles.resultHeader}>
                        <Icon
                          name="check-circle"
                          size={18}
                          color={colors.success}
                        />
                        <Text style={styles.resultHeaderText}>
                          {reportType === "weekly"
                            ? "本周农事报告"
                            : "本月农事报告"}
                        </Text>
                      </View>
                    </FadeInListItem>
                    <FadeInListItem index={1}>
                      <View style={styles.reportCard}>
                        <MarkdownText text={report.content} />
                      </View>
                    </FadeInListItem>
                  </>
                )}
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
    backgroundColor: farmTheme.colors.page,
  },
  scrollContent: {
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.lg,
    flexGrow: 1,
  },
  viewHero: {
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  viewHeroGlow: {
    position: "absolute",
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: "rgba(216, 240, 188, 0.14)",
    right: -42,
    top: -42,
  },
  viewHeroTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  viewHeaderBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255, 255, 255, 0.14)",
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
  },
  viewHeaderTitle: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  viewHeroTitle: {
    fontSize: 24,
    lineHeight: 30,
    color: "#FFFFFF",
    fontWeight: "900",
  },
  viewHeaderDate: {
    marginTop: spacingV2.sm,
    fontSize: fontSizeV2.sm,
    color: "rgba(255, 255, 255, 0.66)",
    fontWeight: "700",
  },
  pageHero: {
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  pageHeroGlow: {
    position: "absolute",
    width: 150,
    height: 150,
    borderRadius: 75,
    backgroundColor: "rgba(216, 240, 188, 0.14)",
    right: -46,
    top: -48,
  },
  pageHeroTop: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacingV2.lg,
  },
  pageHeaderIcon: {
    width: 52,
    height: 52,
    borderRadius: 20,
    backgroundColor: "rgba(255, 255, 255, 0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
  pageHeroBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.full,
    backgroundColor: "rgba(255, 255, 255, 0.10)",
  },
  pageHeroBadgeText: {
    fontSize: fontSizeV2.xs,
    color: "rgba(255, 255, 255, 0.76)",
    fontWeight: "800",
  },
  pageHeaderTitle: {
    fontSize: 25,
    lineHeight: 31,
    fontWeight: "900",
    color: "#FFFFFF",
  },
  pageHeaderSub: {
    fontSize: fontSizeV2.sm,
    color: "rgba(255, 255, 255, 0.72)",
    lineHeight: 21,
    marginTop: spacingV2.sm,
  },
  sectionLabel: {
    fontSize: fontSizeV2.sm,
    fontWeight: "900",
    color: colors.textSecondary,
    marginBottom: spacingV2.sm,
    letterSpacing: 0,
  },
  toggleRow: {
    flexDirection: "row",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  typePill: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.sm,
    paddingVertical: spacingV2.md,
    borderRadius: 22,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  typePillActive: {
    backgroundColor: farmTheme.colors.leafSoft,
    borderColor: "rgba(22, 182, 122, 0.20)",
  },
  typePillText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "800",
  },
  typePillTextActive: {
    color: farmTheme.colors.leaf,
    fontWeight: "900",
  },
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leaf,
    borderRadius: borderRadiusV2.full,
    paddingVertical: spacingV2.lg,
    marginBottom: spacingV2.lg,
    gap: spacingV2.sm,
    shadowColor: farmTheme.colors.leaf,
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.18,
    shadowRadius: 18,
    elevation: 6,
  },
  generateBtnText: {
    color: "#FFFFFF",
    fontSize: fontSizeV2.md,
    fontWeight: "900",
  },
  loadingContainer: {
    alignItems: "center",
    marginTop: spacingV2.lg,
    padding: spacingV2.lg,
    borderRadius: 24,
    backgroundColor: farmTheme.colors.surface,
    ...farmTheme.shadow.card,
  },
  loadingText: {
    marginTop: spacingV2.sm,
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    marginBottom: spacingV2.sm,
  },
  resultHeaderText: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.success,
  },
  reportCard: {
    backgroundColor: farmTheme.colors.surface,
    borderRadius: farmTheme.radius.card,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  summaryCard: {
    flexDirection: "row",
    gap: spacingV2.md,
    padding: spacingV2.lg,
    borderRadius: farmTheme.radius.card,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    marginBottom: spacingV2.lg,
    ...farmTheme.shadow.card,
  },
  summaryIcon: {
    width: 42,
    height: 42,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leafSoft,
  },
  summaryCopy: {
    flex: 1,
    minWidth: 0,
  },
  summaryLabel: {
    fontSize: fontSizeV2.xs,
    color: farmTheme.colors.leaf,
    fontWeight: "900",
    marginBottom: spacingV2.xs,
  },
  summaryText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 21,
    fontWeight: "600",
  },
});
