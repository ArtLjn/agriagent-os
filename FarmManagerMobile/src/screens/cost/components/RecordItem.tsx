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

const TYPE_CONFIG: Record<string, { color: string; bgColor: string; iconColor: string }> = {
  cost: {
    color: colors.expense,
    bgColor: colors.expenseBg,
    iconColor: colors.expense,
  },
  income: {
    color: colors.income,
    bgColor: colors.incomeBg,
    iconColor: colors.income,
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
    iconColor: colors.textSecondary,
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
    isDebt ? (item.counterparty || "赊账") : null,
    getRecordNoteText(item),
  ].filter(Boolean);

  return (
    <TouchableOpacity
      onPress={onPress}
      onLongPress={onLongPress}
      delayLongPress={400}
      activeOpacity={0.65}
      style={styles.container}
    >
      <View style={[styles.iconWrap, { backgroundColor: config.bgColor }]}>
        <Icon name={catIcon} size={20} color={config.iconColor} />
      </View>

      <View style={styles.info}>
        <View style={styles.titleRow}>
          <Text style={styles.category} numberOfLines={1}>
            {item.category}
          </Text>
          {item.source_label ? (
            <Text style={styles.sourceTag} numberOfLines={1}>
              {item.source_label.replace(/^来自/, "")}
            </Text>
          ) : null}
        </View>
        {metaParts.length > 0 && (
          <Text style={styles.meta} numberOfLines={1}>
            {metaParts.join(" · ")}
          </Text>
        )}
      </View>

      <Text
        style={[styles.amount, { color: config.color }]}
        numberOfLines={1}
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
    paddingVertical: 14,
    paddingHorizontal: spacingV2.lg,
    minHeight: 68,
    gap: spacingV2.md,
  },
  iconWrap: {
    width: 42,
    height: 42,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  info: {
    flex: 1,
    minWidth: 0,
    justifyContent: "center",
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
  },
  category: {
    fontSize: fontSizeV2.md,
    fontWeight: "700",
    color: colors.text,
    letterSpacing: -0.2,
  },
  sourceTag: {
    maxWidth: 100,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: borderRadiusV2.full,
    overflow: "hidden",
    backgroundColor: colors.surfaceMuted,
    color: colors.textSecondary,
    fontSize: fontSizeV2.xs,
    fontWeight: "600",
  },
  meta: {
    fontSize: fontSizeV2.sm,
    color: colors.textTertiary,
    marginTop: 3,
    fontWeight: "500",
  },
  amount: {
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: -0.3,
    flexShrink: 0,
    textAlign: "right",
    minWidth: 64,
  },
});
