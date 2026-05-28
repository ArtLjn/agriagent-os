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
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
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
      <Icon name="plus" size={20} color={colors.primary} />
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
    padding: spacingV2.lg,
  },
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
    borderRadius: borderRadiusV2.xl,
    paddingVertical: spacingV2.lg,
    marginBottom: spacingV2.lg,
    gap: spacingV2.sm,
  },
  generateBtnText: {
    color: colors.primary,
    fontSize: fontSizeV2.md,
    fontWeight: "600",
  },
  emptyReports: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
  },
  emptyReportsText: {
    fontSize: fontSizeV2.lg,
    color: colors.textSecondary,
    marginTop: spacingV2.lg,
    fontWeight: "600",
  },
  emptyReportsSub: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: spacingV2.xs,
  },
  reportItem: {
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  reportItemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacingV2.sm,
  },
  reportItemTypeBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: colors.primaryMuted,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.md,
  },
  reportItemType: {
    fontSize: fontSizeV2.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  reportItemDate: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
  reportItemPreview: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    lineHeight: 22,
  },
  reportItemFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacingV2.md,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(0,0,0,0.04)",
  },
  reportItemView: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
});
