import React from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../theme/spacing";

interface BulkActionBarProps {
  selectedCount: number;
  deleting?: boolean;
  onCancel: () => void;
  onDelete: () => void;
}

export const BulkActionBar: React.FC<BulkActionBarProps> = ({
  selectedCount,
  deleting = false,
  onCancel,
  onDelete,
}) => (
  <View style={styles.wrap}>
    <View style={styles.info}>
      <Text style={styles.count}>已选 {selectedCount} 项</Text>
      <Text style={styles.hint}>再次点击卡片可取消选择</Text>
    </View>
    <View style={styles.actions}>
      <TouchableOpacity
        style={styles.cancelBtn}
        activeOpacity={0.75}
        onPress={onCancel}
      >
        <Text style={styles.cancelText}>取消</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.deleteBtn, deleting && styles.deleteBtnDisabled]}
        activeOpacity={0.75}
        onPress={onDelete}
        disabled={deleting || selectedCount === 0}
      >
        <Icon name="trash-can-outline" size={18} color={colors.textInverse} />
        <Text style={styles.deleteText}>{deleting ? "删除中" : "删除"}</Text>
      </TouchableOpacity>
    </View>
  </View>
);

const styles = StyleSheet.create({
  wrap: {
    position: "absolute",
    left: spacingV2.lg,
    right: spacingV2.lg,
    bottom: spacingV2.lg,
    minHeight: 72,
    borderRadius: borderRadiusV2.xxl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderLight,
    paddingHorizontal: spacingV2.lg,
    paddingVertical: spacingV2.md,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 20,
    elevation: 10,
  },
  info: {
    flex: 1,
    paddingRight: spacingV2.md,
  },
  count: {
    color: colors.text,
    fontSize: fontSizeV2.md,
    fontWeight: "800",
  },
  hint: {
    color: colors.textTertiary,
    fontSize: fontSizeV2.xs,
    marginTop: 2,
  },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
  },
  cancelBtn: {
    minWidth: 58,
    height: 40,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceMuted,
  },
  cancelText: {
    color: colors.textSecondary,
    fontSize: fontSizeV2.sm,
    fontWeight: "700",
  },
  deleteBtn: {
    minWidth: 82,
    height: 40,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 4,
    backgroundColor: colors.danger,
  },
  deleteBtnDisabled: {
    opacity: 0.55,
  },
  deleteText: {
    color: colors.textInverse,
    fontSize: fontSizeV2.sm,
    fontWeight: "800",
  },
});
