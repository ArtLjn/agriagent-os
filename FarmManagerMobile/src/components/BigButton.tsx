import React from "react";
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ViewStyle,
  TextStyle,
} from "react-native";
import { colors } from "../theme/colors";
import { spacing, fontSize, borderRadius, shadows } from "../theme/spacing";
import Icon from "react-native-vector-icons/MaterialCommunityIcons";

interface BigButtonProps {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
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
  const bgColors = {
    primary: colors.primary,
    secondary: colors.surface,
    danger: colors.danger,
    ghost: "transparent",
  };

  const textColors = {
    primary: colors.textInverse,
    secondary: colors.text,
    danger: colors.textInverse,
    ghost: colors.primary,
  };

  const borderColors = {
    primary: colors.primary,
    secondary: colors.border,
    danger: colors.danger,
    ghost: colors.primary,
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.8}
      style={[
        styles.button,
        {
          backgroundColor: bgColors[variant],
          borderColor: borderColors[variant],
        },
        variant === "primary" && styles.primaryShadow,
        disabled && styles.disabled,
        style,
      ]}
    >
      {icon && (
        <Icon
          name={icon}
          size={18}
          color={textColors[variant]}
          style={styles.icon}
        />
      )}
      <Text style={[styles.text, { color: textColors[variant] }]}>{title}</Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    flexDirection: "row",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
    borderWidth: 1,
  },
  primaryShadow: {
    ...shadows.sm,
  },
  icon: {
    marginRight: spacing.sm,
  },
  text: {
    fontSize: fontSize.md,
    fontWeight: "600",
  },
  disabled: {
    opacity: 0.5,
  },
});
