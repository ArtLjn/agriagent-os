import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, Modal } from "react-native";
import type { CostRecord } from "../../../api/types";
import { colors } from "../../../theme/colors";
import { spacing, fontSize, borderRadius } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";

interface RecordDetailModalProps {
  visible: boolean;
  record: CostRecord | null;
  onClose: () => void;
  onDelete: () => void;
}

export const RecordDetailModal: React.FC<RecordDetailModalProps> = ({
  visible,
  record,
  onClose,
  onDelete,
}) => {
  if (!record) {
    return null;
  }

  const isCost = record.record_type === "cost";
  const typeLabel = isCost ? "支出" : "收入";
  const typeColor = isCost ? colors.danger : colors.success;
  const typeBg = isCost ? colors.dangerLight : colors.successLight;
  const prefix = isCost ? "-" : "+";

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <TouchableOpacity
          style={styles.backdrop}
          onPress={onClose}
          activeOpacity={1}
        />
        <View style={styles.sheet}>
          {/* 顶部指示条 */}
          <View style={styles.handle} />

          {/* 类型标签 */}
          <View style={[styles.typeBadge, { backgroundColor: typeBg }]}>
            <Text style={[styles.typeText, { color: typeColor }]}>
              {typeLabel}
            </Text>
          </View>

          {/* 金额 */}
          <Text style={[styles.amount, { color: typeColor }]}>
            {prefix}
            {record.amount}
          </Text>

          {/* 详情列表 */}
          <View style={styles.details}>
            <View style={styles.detailRow}>
              <View style={styles.detailLeft}>
                <Icon
                  name="tag-outline"
                  size={18}
                  color={colors.textSecondary}
                />
                <Text style={styles.detailLabel}>分类</Text>
              </View>
              <Text style={styles.detailValue}>{record.category}</Text>
            </View>

            <View style={styles.detailRow}>
              <View style={styles.detailLeft}>
                <Icon
                  name="calendar-outline"
                  size={18}
                  color={colors.textSecondary}
                />
                <Text style={styles.detailLabel}>日期</Text>
              </View>
              <Text style={styles.detailValue}>
                {dayjs(record.record_date).format("YYYY年M月D日")}
              </Text>
            </View>

            {record.note ? (
              <View style={styles.detailRow}>
                <View style={styles.detailLeft}>
                  <Icon
                    name="note-text-outline"
                    size={18}
                    color={colors.textSecondary}
                  />
                  <Text style={styles.detailLabel}>备注</Text>
                </View>
                <Text style={styles.detailValue}>{record.note}</Text>
              </View>
            ) : null}
          </View>

          {/* 操作按钮 */}
          <View style={styles.actions}>
            <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
              <Text style={styles.closeText}>关闭</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.deleteBtn} onPress={onDelete}>
              <Icon name="delete-outline" size={18} color={colors.danger} />
              <Text style={styles.deleteText}>删除</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
};

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: colors.overlay,
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: borderRadius.xl,
    borderTopRightRadius: borderRadius.xl,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    paddingTop: spacing.sm,
    alignItems: "center",
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: borderRadius.full,
    backgroundColor: colors.border,
    marginBottom: spacing.md,
  },
  typeBadge: {
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.sm,
    marginBottom: spacing.md,
  },
  typeText: {
    fontSize: fontSize.sm,
    fontWeight: "700",
  },
  amount: {
    fontSize: 36,
    fontWeight: "800",
    marginBottom: spacing.lg,
  },
  details: {
    width: "100%",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  detailLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  detailLabel: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
  },
  detailValue: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "600",
    maxWidth: "60%",
    textAlign: "right",
  },
  actions: {
    flexDirection: "row",
    width: "100%",
    gap: spacing.md,
  },
  closeBtn: {
    flex: 1,
    paddingVertical: spacing.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadius.lg,
    alignItems: "center",
  },
  closeText: {
    fontSize: fontSize.md,
    color: colors.text,
    fontWeight: "700",
  },
  deleteBtn: {
    flex: 1,
    paddingVertical: spacing.md,
    backgroundColor: colors.dangerLight,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xs,
  },
  deleteText: {
    fontSize: fontSize.md,
    color: colors.danger,
    fontWeight: "700",
  },
});
