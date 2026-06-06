import React from "react";
import { View, Text, StyleSheet } from "react-native";
import { colors } from "../../theme/colors";
import { spacingV2, fontSizeV2 } from "../../theme/spacing";

interface SectionProps {
  title: string;
  children: React.ReactNode;
}

export const Section: React.FC<SectionProps> = ({ title, children }) => {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginBottom: spacingV2.lg,
  },
  title: {
    fontSize: fontSizeV2.md,
    fontWeight: "900",
    color: colors.textSecondary,
    marginBottom: spacingV2.sm,
    marginLeft: spacingV2.xs,
    letterSpacing: 0,
  },
});
