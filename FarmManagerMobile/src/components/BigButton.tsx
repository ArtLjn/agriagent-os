import React from "react";
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ViewStyle,
} from "react-native";
import { colors } from "../theme/colors";
import { spacingV2, fontSizeV2, borderRadiusV2 } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface BigButtonProps {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "ghost";
  disabled?: boolean;
  style?: ViewStyle;
  icon?: string;
}

export const BigButton: React.FC<BigButtonProps> = ({
  title,
  onPress,
  variant = "primary",
  disabled = false,
  style,
  icon,
}) => {
  const isPrimary = variant === "primary";
  const isSecondary = variant === "secondary";

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.7}
      style={[
        styles.button,
        isPrimary && styles.primary,
        isSecondary && styles.secondary,
        disabled && styles.disabled,
        style,
      ]}
    >
      {icon && (
        <Icon
          name={icon}
          size={18}
          color={isPrimary ? colors.primary : colors.text}
          style={styles.icon}
        />
      )}
      <Text
        style={[
          styles.text,
          isPrimary && styles.primaryText,
          isSecondary && styles.secondaryText,
        ]}
      >
        {title}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: "row",
    paddingVertical: 14,
    paddingHorizontal: spacingV2.lg,
    borderRadius: borderRadiusV2.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  primary: {
    backgroundColor: colors.primaryMuted,
  },
  secondary: {
    backgroundColor: colors.surfaceMuted,
  },
  text: {
    fontSize: fontSizeV2.md,
    fontWeight: "600",
  },
  primaryText: {
    color: colors.primary,
  },
  secondaryText: {
    color: colors.text,
  },
  icon: {
    marginRight: spacingV2.sm,
  },
  disabled: {
    opacity: 0.4,
  },
});
