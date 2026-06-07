import React from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface CostMetaPanelProps {
  recordDate: Date;
  isIncome: boolean;
  isDebt: boolean;
  counterparty: string;
  dueDate: Date | null;
  note: string;
  themeColor: string;
  onDatePress: () => void;
  onDebtToggle: () => void;
  onCounterpartyChange: (value: string) => void;
  onDueDatePress: () => void;
  onNoteChange: (value: string) => void;
}

export const CostMetaPanel: React.FC<CostMetaPanelProps> = ({
  recordDate,
  isIncome,
  isDebt,
  counterparty,
  dueDate,
  note,
  themeColor,
  onDatePress,
  onDebtToggle,
  onCounterpartyChange,
  onDueDatePress,
  onNoteChange,
}) => (
  <View style={styles.container}>
    <View style={styles.compactRow}>
      <TouchableOpacity
        style={[styles.compactCard, styles.dateCard]}
        onPress={onDatePress}
        activeOpacity={0.75}
      >
        <View style={styles.iconBox}>
          <Icon name="calendar-clock" size={20} color={colors.primary} />
        </View>
        <View style={styles.compactInfo}>
          <Text style={styles.compactTitle}>日期时间</Text>
          <Text style={styles.compactValue}>
            {dayjs(recordDate).format("M月D日 HH:mm")}
          </Text>
        </View>
        <Icon name="chevron-right" size={18} color={colors.textTertiary} />
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.compactCard}
        onPress={onDebtToggle}
        activeOpacity={0.75}
      >
        <View style={styles.iconBox}>
          <Icon name="hand-coin-outline" size={20} color={colors.primary} />
        </View>
        <View style={styles.compactInfo}>
          <Text style={styles.compactTitle}>
            {isIncome ? "对方先欠着" : "这笔先赊着"}
          </Text>
          <Text style={styles.compactValue}>
            {isIncome ? "应收账款" : "应付账款"}
          </Text>
          <View
            style={[
              styles.toggleTrack,
              isDebt && { backgroundColor: themeColor },
            ]}
          >
            <View
              style={[styles.toggleThumb, isDebt && styles.toggleThumbActive]}
            />
          </View>
        </View>
      </TouchableOpacity>
    </View>

    {isDebt ? (
      <View style={styles.debtPanel}>
        <View style={styles.debtField}>
          <Text style={styles.debtLabel}>{isIncome ? "欠款人" : "债权人"}</Text>
          <TextInput
            style={styles.debtInput}
            placeholder={isIncome ? "如：收购商老李" : "如：老王农资店"}
            placeholderTextColor={colors.textTertiary}
            value={counterparty}
            onChangeText={onCounterpartyChange}
          />
        </View>
        <TouchableOpacity
          style={styles.debtDate}
          onPress={onDueDatePress}
          activeOpacity={0.75}
        >
          <Text style={styles.debtLabel}>预计还款日</Text>
          <Text
            style={[
              styles.debtDateValue,
              !dueDate && { color: colors.textTertiary },
            ]}
          >
            {dueDate ? dayjs(dueDate).format("YYYY-MM-DD") : "请选择日期"}
          </Text>
          <Icon name="chevron-right" size={18} color={colors.textTertiary} />
        </TouchableOpacity>
      </View>
    ) : null}

    <View style={styles.noteBox}>
      <Icon name="pencil-outline" size={18} color={colors.textTertiary} />
      <TextInput
        style={styles.noteInput}
        placeholder="添加备注..."
        placeholderTextColor={colors.textTertiary}
        value={note}
        onChangeText={onNoteChange}
        multiline
        textAlignVertical="top"
      />
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: {
    marginHorizontal: spacingV2.lg,
    gap: spacingV2.md,
  },
  compactRow: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  compactCard: {
    flex: 1,
    minHeight: 78,
    padding: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#EDF0F5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 14,
    elevation: 2,
  },
  dateCard: {
    flex: 1.35,
  },
  iconBox: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primaryMuted,
  },
  compactInfo: {
    flex: 1,
    minWidth: 0,
  },
  compactTitle: {
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  compactValue: {
    marginTop: 2,
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    fontWeight: "500",
  },
  toggleTrack: {
    marginTop: spacingV2.xs,
    width: 42,
    height: 24,
    borderRadius: 12,
    padding: 3,
    backgroundColor: "#E5EAF2",
  },
  toggleThumb: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  toggleThumbActive: {
    transform: [{ translateX: 18 }],
  },
  debtPanel: {
    padding: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    gap: spacingV2.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#EDF0F5",
  },
  debtField: {
    gap: spacingV2.xs,
  },
  debtLabel: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
  debtInput: {
    minHeight: 44,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    color: colors.text,
    backgroundColor: colors.surfaceMuted,
    fontSize: fontSizeV2.md,
    fontWeight: "500",
  },
  debtDate: {
    minHeight: 44,
    borderRadius: borderRadiusV2.lg,
    paddingHorizontal: spacingV2.md,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    backgroundColor: colors.surfaceMuted,
  },
  debtDateValue: {
    flex: 1,
    color: colors.text,
    fontSize: fontSizeV2.md,
    fontWeight: "600",
  },
  noteBox: {
    minHeight: 46,
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacingV2.sm,
    paddingHorizontal: spacingV2.md,
    paddingVertical: spacingV2.sm,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#EDF0F5",
  },
  noteInput: {
    flex: 1,
    minHeight: 28,
    maxHeight: 86,
    padding: 0,
    color: colors.text,
    fontSize: fontSizeV2.md,
    fontWeight: "500",
  },
});
