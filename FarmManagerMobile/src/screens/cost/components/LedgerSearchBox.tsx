import React from "react";
import { View, TextInput, TouchableOpacity, StyleSheet } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

import { colors } from "../../../theme/colors";
import { borderRadiusV2, fontSizeV2, spacingV2 } from "../../../theme/spacing";

interface LedgerSearchBoxProps {
  value: string;
  onChange: (value: string) => void;
}

export const LedgerSearchBox: React.FC<LedgerSearchBoxProps> = ({
  value,
  onChange,
}) => (
  <View style={styles.searchSection}>
    <View style={styles.searchBox}>
      <Icon name="magnify" size={18} color={colors.textTertiary} />
      <TextInput
        style={styles.searchInput}
        placeholder="搜索账单..."
        placeholderTextColor={colors.textTertiary}
        value={value}
        onChangeText={onChange}
        returnKeyType="search"
      />
      {value.length > 0 ? (
        <TouchableOpacity
          onPress={() => onChange("")}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Icon name="close-circle" size={16} color={colors.textTertiary} />
        </TouchableOpacity>
      ) : null}
    </View>
  </View>
);

const styles = StyleSheet.create({
  searchSection: {
    paddingHorizontal: spacingV2.lg,
    marginBottom: spacingV2.md,
  },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacingV2.sm,
    minHeight: 44,
    paddingHorizontal: spacingV2.md,
    borderRadius: borderRadiusV2.xl,
    backgroundColor: colors.surface,
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    paddingVertical: spacingV2.sm,
    fontSize: fontSizeV2.md,
    color: colors.text,
    fontWeight: "500",
  },
});
