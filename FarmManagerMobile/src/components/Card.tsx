import React from 'react';
import {View, StyleSheet, ViewStyle} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, borderRadius, shadows} from '../theme/spacing';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle | ViewStyle[];
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  style,
  padding = 'md',
  elevated = true,
}) => {
  const paddingMap = {none: 0, sm: spacing.sm, md: spacing.md, lg: spacing.lg};
  return (
    <View
      style={[
        styles.card,
        {padding: paddingMap[padding]},
        elevated && styles.elevated,
        style,
      ]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  elevated: {
    ...shadows.md,
  },
});
