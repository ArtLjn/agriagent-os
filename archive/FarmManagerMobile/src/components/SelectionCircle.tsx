import React from "react";
import { StyleSheet, View } from "react-native";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";
import { colors } from "../theme/colors";

interface SelectionCircleProps {
  selected: boolean;
}

export const SelectionCircle: React.FC<SelectionCircleProps> = ({
  selected,
}) => (
  <View style={[styles.circle, selected && styles.circleSelected]}>
    {selected && <Icon name="check" size={16} color={colors.textInverse} />}
  </View>
);

const styles = StyleSheet.create({
  circle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  circleSelected: {
    borderColor: colors.primary,
    backgroundColor: colors.primary,
  },
});
