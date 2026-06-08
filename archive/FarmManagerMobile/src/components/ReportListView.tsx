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
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { BulkActionBar } from "./BulkActionBar";
import { SelectionCircle } from "./SelectionCircle";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { showAlert } from "../utils/alert";

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
          <TouchableOpacity
            style={styles.generateBtn}
            onPress={onGenerate}
            activeOpacity={0.7}
          >
            <Icon name="plus" size={20} color={colors.primary} />
            <Text style={styles.generateBtnText}>生成新报告</Text>
          </TouchableOpacity>
        )}
        {reports.length === 0 ? (
          <View style={styles.emptyReports}>
            <Icon
              name="file-document-outline"
              size={48}
              color={colors.textTertiary}
            />
            <Text style={styles.emptyReportsText}>暂无报告</Text>
            <Text style={styles.emptyReportsSub}>
              点击上方按钮生成第一份报告
            </Text>
          </View>
        ) : (
          reports.map((r) => (
            <View key={r.id} style={styles.selectableRow}>
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
                activeOpacity={0.7}
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
                  <Icon
                    name="chevron-right"
                    size={16}
                    color={colors.textTertiary}
                  />
                </View>
              </TouchableOpacity>
            </View>
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
  },
  reportListContentSelecting: {
    paddingBottom: 104,
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
    flex: 1,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.xl,
    padding: spacingV2.lg,
  },
  reportItemSelected: {
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: "#FBFCFF",
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
