import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface CostCreateHeroHeaderProps {
  onBack: () => void;
}

export const CostCreateHeroHeader: React.FC<CostCreateHeroHeaderProps> = ({
  onBack,
}) => (
  <View style={styles.header}>
    <TouchableOpacity
      style={styles.backButton}
      onPress={onBack}
      activeOpacity={0.75}
    >
      <Icon name="chevron-left" size={22} color={colors.text} />
    </TouchableOpacity>
    <Text style={styles.title}>记一笔</Text>
    <View style={styles.smartPill}>
      <Icon name="auto-fix" size={14} color={colors.primary} />
      <Text style={styles.smartText}>智能识别</Text>
    </View>
  </View>
);

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacingV2.lg,
    paddingTop: spacingV2.sm,
    paddingBottom: spacingV2.sm,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacingV2.md,
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  title: {
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "700",
    letterSpacing: -0.3,
  },
  smartPill: {
    height: 34,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.full,
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.xs,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "rgba(74,123,247,0.14)",
  },
  smartText: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "600",
  },
});
