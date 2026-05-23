import React from 'react';
import {TouchableOpacity, Text, StyleSheet, ViewStyle, TextStyle} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, fontSize, borderRadius} from '../theme/spacing';

interface BigButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  disabled?: boolean;
  style?: ViewStyle;
}

export const BigButton: React.FC<BigButtonProps> = ({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  style,
}) => {
  const bgColors = {
    primary: colors.primary,
    secondary: colors.surface,
    danger: colors.danger,
  };

  const textColors = {
    primary: colors.textInverse,
    secondary: colors.text,
    danger: colors.textInverse,
  };

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={disabled}
      activeOpacity={0.8}
      style={[
        styles.button,
        {backgroundColor: bgColors[variant]},
        disabled && styles.disabled,
        style,
      ]}>
      <Text style={[styles.text, {color: textColors[variant]}]}>{title}</Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.lg,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
  },
  text: {
    fontSize: fontSize.lg,
    fontWeight: '600',
  },
  disabled: {
    opacity: 0.5,
  },
});
