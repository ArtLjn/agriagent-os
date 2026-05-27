import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import type { ReportListItem } from "../api/types";
import { colors } from "../theme/colors";
import { spacing, fontSize, borderRadius } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface ReportListViewProps {
  reports: ReportListItem[];
  onGenerate: () => void;
  onViewReport: (r: ReportListItem) => void;
}

export const ReportListView: React.FC<ReportListViewProps> = ({
  reports,
  onGenerate,
  onViewReport,
}) => (
  <ScrollView
    style={styles.reportList}
    contentContainerStyle={styles.reportListContent}
  >
    <TouchableOpacity
      style={styles.generateBtn}
      onPress={onGenerate}
      activeOpacity={0.7}
    >
      <Icon name="plus" size={20} color="#FFFFFF" />
      <Text style={styles.generateBtnText}>生成新报告</Text>
    </TouchableOpacity>
    {reports.length === 0 ? (
      <View style={styles.emptyReports}>
        <Icon
          name="file-document-outline"
          size={48}
          color={colors.textTertiary}
        />
        <Text style={styles.emptyReportsText}>暂无报告</Text>
        <Text style={styles.emptyReportsSub}>点击上方按钮生成第一份报告</Text>
      </View>
    ) : (
      reports.map((r) => (
        <TouchableOpacity
          key={r.id}
          style={styles.reportItem}
          activeOpacity={0.7}
          onPress={() => onViewReport(r)}
        >
          <View style={styles.reportItemHeader}>
            <View style={styles.reportItemTypeBadge}>
              <Icon
                name={
                  r.report_type === "weekly"
                    ? "calendar-week"
                    : "calendar-month"
                }
                size={14}
                color={colors.primary}
              />
              <Text style={styles.reportItemType}>
                {r.report_type === "weekly" ? "周报" : "月报"}
              </Text>
            </View>
            <Text style={styles.reportItemDate}>
              {new Date(r.created_at).toLocaleDateString("zh-CN")}
            </Text>
          </View>
          <Text style={styles.reportItemPreview} numberOfLines={2}>
            {r.content}
          </Text>
          <View style={styles.reportItemFooter}>
            <Text style={styles.reportItemView}>点击查看详情</Text>
            <Icon name="chevron-right" size={16} color={colors.textTertiary} />
          </View>
        </TouchableOpacity>
      ))
    )}
  </ScrollView>
);

const styles = StyleSheet.create({
  reportList: {
    flex: 1,
  },
  reportListContent: {
    padding: spacing.md,
  },
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.lg,
    paddingVertical: spacing.md,
    marginBottom: spacing.md,
    gap: spacing.sm,
  },
  generateBtnText: {
    color: "#FFFFFF",
    fontSize: fontSize.md,
    fontWeight: "700",
  },
  emptyReports: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyReportsText: {
    fontSize: fontSize.lg,
    color: colors.textSecondary,
    marginTop: spacing.md,
    fontWeight: "600",
  },
  emptyReportsSub: {
    fontSize: fontSize.sm,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
  reportItem: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  reportItemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.sm,
  },
  reportItemTypeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.sm,
  },
  reportItemType: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.primary,
  },
  reportItemDate: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
  },
  reportItemPreview: {
    fontSize: fontSize.sm,
    color: colors.textSecondary,
    lineHeight: 20,
  },
  reportItemFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.borderLight,
  },
  reportItemView: {
    fontSize: fontSize.xs,
    color: colors.textTertiary,
  },
});
