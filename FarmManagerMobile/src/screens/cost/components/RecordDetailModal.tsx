import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, Modal } from "react-native";
import type { CostRecord } from "../../../api/types";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";
import { formatRecordTimestamp } from "../utils/recordDisplay";

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
  const typeColor = isCost ? colors.expense : colors.income;
  const typeBg = isCost ? colors.expenseBg : colors.incomeBg;
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
          <View style={styles.handle} />

          <View style={[styles.typeBadge, { backgroundColor: typeBg }]}>
            <Text style={[styles.typeText, { color: typeColor }]}>
              {typeLabel}
            </Text>
          </View>

          <Text style={[styles.amount, { color: typeColor }]}>
            {prefix}
            {record.amount}
          </Text>

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
                {formatRecordTimestamp(record)}
              </Text>
            </View>

            {record.created_at ? (
              <View style={styles.detailRow}>
                <View style={styles.detailLeft}>
                  <Icon
                    name="clock-outline"
                    size={18}
                    color={colors.textSecondary}
                  />
                  <Text style={styles.detailLabel}>创建时间</Text>
                </View>
                <Text style={styles.detailValue}>
                  {dayjs(record.created_at).format("YYYY年M月D日 HH:mm")}
                </Text>
              </View>
            ) : null}

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
    borderTopLeftRadius: borderRadiusV2.xxl,
    borderTopRightRadius: borderRadiusV2.xxl,
    paddingHorizontal: spacingV2.lg,
    paddingBottom: spacingV2.xxxl,
    paddingTop: spacingV2.sm,
    alignItems: "center",
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: borderRadiusV2.full,
    backgroundColor: colors.border,
    marginBottom: spacingV2.lg,
  },
  typeBadge: {
    paddingVertical: spacingV2.xs,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.sm,
    marginBottom: spacingV2.md,
  },
  typeText: {
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
  },
  amount: {
    fontSize: 36,
    fontWeight: "800",
    marginBottom: spacingV2.lg,
  },
  details: {
    width: "100%",
    gap: spacingV2.md,
    marginBottom: spacingV2.lg,
  },
  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacingV2.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  detailLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  detailLabel: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
  },
  detailValue: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "600",
    maxWidth: "60%",
    textAlign: "right",
  },
  actions: {
    flexDirection: "row",
    width: "100%",
    gap: spacingV2.md,
  },
  closeBtn: {
    flex: 1,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.surfaceMuted,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
  },
  closeText: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "700",
  },
  deleteBtn: {
    flex: 1,
    paddingVertical: spacingV2.md,
    backgroundColor: colors.dangerLight,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: spacingV2.xs,
  },
  deleteText: {
    fontSize: fontSizeV2.md,
    color: colors.danger,
    fontWeight: "700",
  },
});
