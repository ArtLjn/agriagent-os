import React from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
} from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

const QUICK_AMOUNTS = ["50", "100", "200", "500"];

interface CostAmountPanelProps {
  amount: string;
  recordType: "cost" | "income";
  onAmountChange: (value: string) => void;
  onTypeChange: (type: "cost" | "income") => void;
}

export const CostAmountPanel: React.FC<CostAmountPanelProps> = ({
  amount,
  recordType,
  onAmountChange,
  onTypeChange,
}) => {
  const isIncome = recordType === "income";
  const accentColor = isIncome ? colors.income : colors.expense;

  return (
    <View style={styles.panel}>
      <View style={styles.typeToggle}>
        <TouchableOpacity
          style={[
            styles.typeButton,
            !isIncome && styles.typeButtonActive,
          ]}
          onPress={() => onTypeChange("cost")}
          activeOpacity={0.75}
        >
          <Icon
            name="arrow-bottom-left"
            size={18}
            color={!isIncome ? colors.expense : colors.textTertiary}
          />
          <Text
            style={[
              styles.typeText,
              !isIncome && { color: colors.expense, fontWeight: "800" },
            ]}
          >
            支出
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[
            styles.typeButton,
            isIncome && styles.typeButtonActive,
          ]}
          onPress={() => onTypeChange("income")}
          activeOpacity={0.75}
        >
          <Icon
            name="arrow-top-right"
            size={18}
            color={isIncome ? colors.income : colors.textTertiary}
          />
          <Text
            style={[
              styles.typeText,
              isIncome && { color: colors.income, fontWeight: "800" },
            ]}
          >
            收入
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.amountRow}>
        <Text style={[styles.symbol, { color: accentColor }]}>¥</Text>
        <TextInput
          style={[styles.amountInput, { color: accentColor }]}
          placeholder="0"
          placeholderTextColor={colors.textSecondary}
          keyboardType="decimal-pad"
          value={amount}
          onChangeText={onAmountChange}
          textAlign="center"
        />
      </View>

      <View style={styles.quickRow}>
        {QUICK_AMOUNTS.map((value) => (
          <TouchableOpacity
            key={value}
            style={styles.quickChip}
            onPress={() => onAmountChange(value)}
            activeOpacity={0.75}
          >
            <Text style={styles.quickText}>¥{value}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  panel: {
    marginHorizontal: spacingV2.lg,
    marginTop: spacingV2.md,
    marginBottom: spacingV2.xl,
    padding: spacingV2.lg,
    paddingBottom: spacingV2.xl,
    borderRadius: borderRadiusV2.xxxl,
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 16,
    elevation: 3,
  },
  typeToggle: {
    height: 42,
    flexDirection: "row",
    gap: spacingV2.xs,
    padding: spacingV2.xs,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.surfaceMuted,
  },
  typeButton: {
    flex: 1,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: spacingV2.xs,
  },
  typeButtonActive: {
    backgroundColor: colors.surface,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  typeText: {
    fontSize: fontSizeV2.md,
    color: colors.textTertiary,
    fontWeight: "600",
  },
  amountRow: {
    marginTop: spacingV2.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  symbol: {
    fontSize: fontSizeV2.xxxl,
    fontWeight: "700",
    marginRight: spacingV2.xs,
  },
  amountInput: {
    minWidth: 140,
    maxWidth: "78%",
    padding: 0,
    fontSize: 48,
    lineHeight: 54,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  quickRow: {
    marginTop: spacingV2.md,
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  quickChip: {
    flex: 1,
    height: 36,
    borderRadius: borderRadiusV2.full,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceMuted,
  },
  quickText: {
    fontSize: fontSizeV2.md,
    color: colors.textSecondary,
    fontWeight: "700",
  },
});
