import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface CostCategoryPickerProps {
  categories: string[];
  selectedCategory: string;
  themeColor: string;
  themeMuted: string;
  icons: Record<string, string>;
  onSelect: (category: string) => void;
  onMore: () => void;
}

export const CostCategoryPicker: React.FC<CostCategoryPickerProps> = ({
  categories,
  selectedCategory,
  themeColor,
  themeMuted,
  icons,
  onSelect,
  onMore,
}) => (
  <View style={styles.container}>
    <View style={styles.header}>
      <Text style={styles.title}>选择分类</Text>
      <TouchableOpacity onPress={onMore} activeOpacity={0.75}>
        <Text style={styles.manageText}>管理分类</Text>
      </TouchableOpacity>
    </View>
    <View style={styles.grid}>
      {categories.slice(0, 4).map((cat) => {
        const active = selectedCategory === cat;
        return (
          <TouchableOpacity
            key={cat}
            style={[
              styles.card,
              active && {
                backgroundColor: themeMuted,
                borderColor: themeColor + "30",
              },
            ]}
            onPress={() => onSelect(cat)}
            activeOpacity={0.75}
          >
            <View
              style={[
                styles.iconBox,
                active && { backgroundColor: colors.surface },
              ]}
            >
              <Icon
                name={icons[cat] || "tag-outline"}
                size={22}
                color={active ? themeColor : colors.textSecondary}
              />
            </View>
            <Text style={[styles.cardText, active && { color: themeColor }]}>
              {cat}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  </View>
);

const styles = StyleSheet.create({
  container: {
    marginHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  header: {
    height: 34,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  title: {
    fontSize: fontSizeV2.lg,
    color: colors.text,
    fontWeight: "800",
    letterSpacing: -0.3,
  },
  manageText: {
    fontSize: fontSizeV2.sm,
    color: colors.primary,
    fontWeight: "600",
  },
  grid: {
    flexDirection: "row",
    gap: spacingV2.sm,
  },
  card: {
    flex: 1,
    minHeight: 80,
    paddingVertical: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    alignItems: "center",
    justifyContent: "center",
    gap: spacingV2.xs,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: "#EDF0F5",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 14,
    elevation: 2,
  },
  iconBox: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceMuted,
  },
  cardText: {
    fontSize: fontSizeV2.sm,
    color: colors.textSecondary,
    fontWeight: "600",
  },
});
