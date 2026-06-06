import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import type { ReportListItem } from "../api/types";
import { colors } from "../theme/colors";
import { farmTheme } from "../theme/farmTheme";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { BulkActionBar } from "./BulkActionBar";
import { SelectionCircle } from "./SelectionCircle";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { showAlert } from "../utils/alert";
import { FadeInListItem } from "./animations/FadeInListItem";
import { ScalePress } from "./animations/ScalePress";

interface ReportListViewProps {
  reports: ReportListItem[];
  onGenerate: () => void;
  onViewReport: (r: ReportListItem) => void;
  onDeleteReports: (ids: number[]) => Promise<void>;
}

export const ReportListView: React.FC<ReportListViewProps> = ({
  reports,
  onGenerate,
  onViewReport,
  onDeleteReports,
}) => {
  const [deleting, setDeleting] = useState(false);
  const selection = useBulkSelection<number>();

  const handleDeleteSelected = () => {
    showAlert(
      "删除报告",
      `确定删除选中的 ${selection.selectedCount} 份报告吗？`,
      [
        { text: "取消", style: "cancel" },
        {
          text: "删除",
          style: "destructive",
          onPress: async () => {
            setDeleting(true);
            try {
              await onDeleteReports(selection.selectedIds);
              selection.clearSelection();
            } catch (err: any) {
              showAlert("删除失败", err.message || "请稍后重试");
            } finally {
              setDeleting(false);
            }
          },
        },
      ]
    );
  };

  const latestReport = reports[0];
  const getReportLabel = (type: string) =>
    type === "weekly" ? "周报" : "月报";
  const getReportIcon = (type: string) =>
    type === "weekly" ? "calendar-week" : "calendar-month";
  const formatReportDate = (date: string) =>
    new Date(date).toLocaleDateString("zh-CN", {
      month: "long",
      day: "numeric",
    });

  return (
    <View style={styles.root}>
      <ScrollView
        style={styles.reportList}
        contentContainerStyle={[
          styles.reportListContent,
          selection.isSelecting && styles.reportListContentSelecting,
        ]}
      >
        {!selection.isSelecting && (
          <>
            <View style={styles.reportHero}>
              <View style={styles.reportHeroGlow} />
              <View style={styles.reportHeroIcon}>
                <Icon name="file-chart-outline" size={28} color="#FFFFFF" />
              </View>
              <Text style={styles.reportHeroEyebrow}>经营复盘</Text>
              <Text style={styles.reportHeroTitle}>农事报告中心</Text>
              <Text style={styles.reportHeroMeta}>
                {latestReport
                  ? `最近更新 ${formatReportDate(latestReport.created_at)}`
                  : "生成第一份报告后，芽芽会自动汇总农事和账本"}
              </Text>
            </View>

            <ScalePress onPress={onGenerate}>
              <View style={styles.generateBtn}>
                <View style={styles.generateBtnIcon}>
                  <Icon
                    name="auto-fix"
                    size={20}
                    color={farmTheme.colors.leaf}
                  />
                </View>
                <View style={styles.generateBtnCopy}>
                  <Text style={styles.generateBtnText}>生成新报告</Text>
                  <Text style={styles.generateBtnMeta}>
                    自动整理茬口、农事记录和收支
                  </Text>
                </View>
                <Icon
                  name="chevron-right"
                  size={20}
                  color={colors.textTertiary}
                />
              </View>
            </ScalePress>
          </>
        )}
        {reports.length === 0 ? (
          <View style={styles.emptyReports}>
            <View style={styles.emptyReportsIcon}>
              <Icon
                name="file-document-plus-outline"
                size={32}
                color={farmTheme.colors.leaf}
              />
            </View>
            <Text style={styles.emptyReportsText}>还没有报告</Text>
            <Text style={styles.emptyReportsSub}>
              生成后可以在这里回看周报、月报和经营建议。
            </Text>
          </View>
        ) : (
          reports.map((r, index) => (
            <FadeInListItem key={r.id} index={index}>
              <View style={styles.selectableRow}>
                {selection.isSelecting && (
                  <View style={styles.selectionSlot}>
                    <SelectionCircle selected={selection.isSelected(r.id)} />
                  </View>
                )}
                <TouchableOpacity
                  style={[
                    styles.reportItem,
                    selection.isSelected(r.id) && styles.reportItemSelected,
                  ]}
                  activeOpacity={0.78}
                  onLongPress={() => selection.beginSelection(r.id)}
                  onPress={() => {
                    if (selection.isSelecting) {
                      selection.toggleSelection(r.id);
                      return;
                    }
                    onViewReport(r);
                  }}
                >
                  <View style={styles.reportItemHeader}>
                    <View style={styles.reportItemTypeBadge}>
                      <Icon
                        name={getReportIcon(r.report_type)}
                        size={15}
                        color={farmTheme.colors.leaf}
                      />
                      <Text style={styles.reportItemType}>
                        {getReportLabel(r.report_type)}
                      </Text>
                    </View>
                    <Text style={styles.reportItemDate}>
                      {formatReportDate(r.created_at)}
                    </Text>
                  </View>
                  <Text style={styles.reportItemTitle} numberOfLines={1}>
                    {r.report_type === "weekly"
                      ? "本周农事复盘"
                      : "本月经营复盘"}
                  </Text>
                  <Text style={styles.reportItemPreview} numberOfLines={2}>
                    {r.structured_data?.summary || r.content}
                  </Text>
                  <View style={styles.reportItemFooter}>
                    <Text style={styles.reportItemView}>查看完整报告</Text>
                    <Icon
                      name="chevron-right"
                      size={18}
                      color={farmTheme.colors.leaf}
                    />
                  </View>
                </TouchableOpacity>
              </View>
            </FadeInListItem>
          ))
        )}
      </ScrollView>
      {selection.isSelecting && (
        <BulkActionBar
          selectedCount={selection.selectedCount}
          deleting={deleting}
          onCancel={selection.clearSelection}
          onDelete={handleDeleteSelected}
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  reportList: {
    flex: 1,
  },
  reportListContent: {
    padding: spacingV2.lg,
    paddingBottom: 116,
  },
  reportListContentSelecting: {
    paddingBottom: 104,
  },
  generateBtn: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: farmTheme.colors.surface,
    borderRadius: 24,
    padding: spacingV2.md,
    marginBottom: spacingV2.lg,
    gap: spacingV2.md,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  reportHero: {
    minHeight: 152,
    borderRadius: farmTheme.radius.panel,
    backgroundColor: "#254130",
    padding: spacingV2.lg,
    marginBottom: spacingV2.lg,
    overflow: "hidden",
    ...farmTheme.shadow.float,
  },
  reportHeroGlow: {
    position: "absolute",
    width: 140,
    height: 140,
    borderRadius: 70,
    backgroundColor: "rgba(216, 240, 188, 0.14)",
    right: -42,
    top: -42,
  },
  reportHeroIcon: {
    width: 50,
    height: 50,
    borderRadius: 18,
    backgroundColor: "rgba(255, 255, 255, 0.14)",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacingV2.md,
  },
  reportHeroEyebrow: {
    fontSize: fontSizeV2.xs,
    color: "rgba(228, 242, 214, 0.72)",
    fontWeight: "800",
    marginBottom: spacingV2.xs,
  },
  reportHeroTitle: {
    fontSize: 24,
    lineHeight: 30,
    color: "#FFFFFF",
    fontWeight: "900",
  },
  reportHeroMeta: {
    marginTop: spacingV2.sm,
    fontSize: fontSizeV2.xs,
    lineHeight: 18,
    color: "rgba(255, 255, 255, 0.66)",
    fontWeight: "600",
  },
  generateBtnIcon: {
    width: 42,
    height: 42,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leafSoft,
  },
  generateBtnCopy: {
    flex: 1,
    minWidth: 0,
  },
  generateBtnText: {
    color: farmTheme.colors.ink,
    fontSize: fontSizeV2.md,
    fontWeight: "900",
  },
  generateBtnMeta: {
    marginTop: 3,
    color: colors.textSecondary,
    fontSize: fontSizeV2.xs,
    fontWeight: "600",
  },
  emptyReports: {
    alignItems: "center",
    paddingVertical: spacingV2.xxxl,
    paddingHorizontal: spacingV2.lg,
    borderRadius: 26,
    backgroundColor: farmTheme.colors.surface,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  emptyReportsIcon: {
    width: 64,
    height: 64,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: farmTheme.colors.leafSoft,
  },
  emptyReportsText: {
    fontSize: fontSizeV2.lg,
    color: farmTheme.colors.ink,
    marginTop: spacingV2.lg,
    fontWeight: "900",
  },
  emptyReportsSub: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: spacingV2.xs,
    textAlign: "center",
    lineHeight: 20,
  },
  reportItem: {
    flex: 1,
    backgroundColor: farmTheme.colors.surface,
    borderRadius: 24,
    padding: spacingV2.lg,
    borderWidth: 1,
    borderColor: farmTheme.colors.line,
    ...farmTheme.shadow.card,
  },
  reportItemSelected: {
    borderWidth: 1,
    borderColor: farmTheme.colors.leaf,
    backgroundColor: farmTheme.colors.leafSoft,
  },
  selectableRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacingV2.md,
  },
  selectionSlot: {
    width: 36,
    alignItems: "flex-start",
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
    backgroundColor: farmTheme.colors.leafSoft,
    paddingHorizontal: spacingV2.sm,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.md,
  },
  reportItemType: {
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
    color: farmTheme.colors.leaf,
  },
  reportItemDate: {
    fontSize: fontSizeV2.xs,
    color: colors.textTertiary,
  },
  reportItemTitle: {
    fontSize: fontSizeV2.md,
    color: farmTheme.colors.ink,
    fontWeight: "900",
    marginBottom: spacingV2.xs,
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
    color: farmTheme.colors.leaf,
    fontWeight: "800",
  },
});
