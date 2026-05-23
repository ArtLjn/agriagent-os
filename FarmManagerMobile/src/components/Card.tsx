import React from 'react';
import {View, StyleSheet, ViewStyle} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, borderRadius} from '../theme/spacing';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  padding?: 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({children, style, padding = 'md'}) => {
  const paddingMap = {sm: spacing.sm, md: spacing.md, lg: spacing.lg};
  return (
    <View style={[styles.card, {padding: paddingMap[padding]}, style]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: borderRadius.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
