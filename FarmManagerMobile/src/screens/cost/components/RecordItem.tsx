import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import type { CostRecord } from "../../../api/types";
import { Card } from "../../../components/Card";
import { colors } from "../../../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../../../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import dayjs from "dayjs";

const TYPE_CONFIG: Record<
  string,
  { label: string; color: string; icon: string; bgColor: string }
> = {
  cost: {
    label: "支出",
    color: "#C45B5B",
    icon: "arrow-down-circle",
    bgColor: "#FDF0F0",
  },
  income: {
    label: "收入",
    color: "#3B8B5C",
    icon: "arrow-up-circle",
    bgColor: "#E8F5ED",
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

const formatDate = (dateStr: string): string => {
  const d = dayjs(dateStr);
  const today = dayjs();
  if (d.isSame(today, "day")) {
    return "今天";
  }
  if (d.isSame(today.subtract(1, "day"), "day")) {
    return "昨天";
  }
  if (d.year() === today.year()) {
    return d.format("M月D日");
  }
  return d.format("YYYY年M月D日");
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
    label: item.record_type,
    color: colors.textSecondary,
    icon: "help-circle",
    bgColor: colors.surfaceMuted,
  };
  const catIcon = CATEGORY_ICONS[item.category] || "tag";
  const isCost = item.record_type === "cost";
  const prefix = isCost ? "-" : "+";

  return (
    <TouchableOpacity
      onPress={onPress}
      onLongPress={onLongPress}
      delayLongPress={400}
      activeOpacity={0.7}
    >
      <Card style={styles.card}>
        <View style={styles.row}>
          <View style={styles.left}>
            <View style={styles.categoryRow}>
              <View
                style={[styles.typeIcon, { backgroundColor: config.bgColor }]}
              >
                <Icon name={catIcon} size={18} color={config.color} />
              </View>
              <View>
                <Text style={styles.category}>{item.category}</Text>
                <Text style={styles.date}>{formatDate(item.record_date)}</Text>
              </View>
            </View>
          </View>
          <View style={styles.right}>
            <Text style={[styles.amount, { color: config.color }]}>
              {prefix}
              {item.amount}
            </Text>
            <View
              style={[styles.typeBadge, { backgroundColor: config.bgColor }]}
            >
              <Text style={[styles.typeText, { color: config.color }]}>
                {config.label}
              </Text>
            </View>
          </View>
        </View>
        {item.note ? (
          <View style={styles.noteRow}>
            <Icon
              name="note-text-outline"
              size={12}
              color={colors.textTertiary}
            />
            <Text style={styles.note} numberOfLines={1}>
              {item.note}
            </Text>
          </View>
        ) : null}
      </Card>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    marginBottom: spacingV2.sm,
    padding: spacingV2.lg,
    backgroundColor: colors.surface,
    borderRadius: borderRadiusV2.xl,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.03,
    shadowRadius: 6,
    elevation: 1,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  left: {
    flex: 1,
  },
  categoryRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.md,
  },
  typeIcon: {
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  category: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
    color: colors.text,
  },
  date: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    marginTop: 2,
  },
  right: {
    alignItems: "flex-end",
  },
  amount: {
    fontSize: fontSizeV2.lg,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  typeBadge: {
    marginTop: spacingV2.xs,
    paddingVertical: 2,
    paddingHorizontal: spacingV2.sm,
    borderRadius: 6,
  },
  typeText: {
    fontSize: fontSizeV2.xs,
    fontWeight: "600",
  },
  noteRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: spacingV2.md,
    paddingTop: spacingV2.md,
    borderTopWidth: 1,
    borderTopColor: "rgba(0,0,0,0.04)",
    gap: spacingV2.xs,
  },
  note: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    flex: 1,
  },
});
