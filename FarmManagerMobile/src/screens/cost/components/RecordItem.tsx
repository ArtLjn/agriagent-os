import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { CostRecord } from "../../../api/types";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import {
  formatRecordAmount,
  getRecordNoteText,
  getRecordTimeText,
} from "../utils/recordDisplay";

const TYPE_CONFIG: Record<string, { color: string; bgColor: string }> = {
  cost: {
    color: colors.expense,
    bgColor: colors.expenseBg,
  },
  income: {
    color: colors.income,
    bgColor: colors.incomeBg,
  },
};

const CATEGORY_ICONS: Record<string, string> = {
  种子: "seed",
  化肥: "flask",
  农药: "spray",
  人工: "account-hard-hat",
  水电: "flash",
  地租: "home-variant",
  销售: "cash",
  补贴: "gift",
  其他: "dots-horizontal",
};

const PAYMENT_LABELS: Record<string, string> = {
  cash: "现金",
  wechat: "微信",
  bank_card: "银行卡",
  debt: "赊账",
};

interface RecordItemProps {
  item: CostRecord;
  onPress: () => void;
  onLongPress?: () => void;
}

export const RecordItem: React.FC<RecordItemProps> = ({
  item,
  onPress,
  onLongPress,
}) => {
  const config = TYPE_CONFIG[item.record_type] || {
    color: colors.textSecondary,
    bgColor: colors.surfaceMuted,
  };
  const catIcon = CATEGORY_ICONS[item.category] || "tag";
  const isCost = item.record_type === "cost";
  const prefix = isCost ? "-" : "+";
  const paymentMethod = (item as CostRecord & { payment_method?: string })
    .payment_method;
  const isDebt = Boolean(item.record_subtype || item.counterparty);
  const metaParts = [
    getRecordTimeText(item),
    paymentMethod ? PAYMENT_LABELS[paymentMethod] || paymentMethod : null,
    isDebt ? item.counterparty || "赊账" : null,
    getRecordNoteText(item),
  ].filter(Boolean);

  return (
    <TouchableOpacity
      onPress={onPress}
      onLongPress={onLongPress}
      delayLongPress={400}
      activeOpacity={0.7}
      style={styles.container}
    >
      <View style={styles.left}>
        <View style={[styles.iconCircle, { backgroundColor: config.bgColor }]}>
          <Icon name={catIcon} size={18} color={config.color} />
        </View>
        <View style={styles.info}>
          <Text style={styles.category}>{item.category}</Text>
          <Text style={styles.meta} numberOfLines={1}>
            {metaParts.join(" · ")}
          </Text>
        </View>
      </View>
      <Text
        style={[styles.amount, { color: config.color }]}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.72}
      >
        {prefix}
        {formatRecordAmount(item.amount)}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xxl,
    padding: spacingV2.lg,
    marginBottom: spacingV2.sm,
    shadowColor: colors.shadow,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  left: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
    flex: 1,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  info: {
    flex: 1,
    minWidth: 0,
  },
  category: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  meta: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  amount: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    letterSpacing: -0.3,
    maxWidth: 132,
    flexShrink: 0,
    textAlign: "right",
  },
});
