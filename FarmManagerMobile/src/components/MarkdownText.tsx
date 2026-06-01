import React from "react";
import Markdown, { MarkdownIt } from "react-native-markdown-display";
import { View, ScrollView } from "react-native";
import { colors } from "../theme/colors";
import { spacing, fontSize, borderRadius } from "../theme/spacing";

interface MarkdownTextProps {
  text: string;
  baseStyle?: object;
}

const tableRules = {
  table: (node: any, children: any, parent: any, styles: any) => (
    <ScrollView
      key={node.key}
      horizontal
      showsHorizontalScrollIndicator
      style={{ marginVertical: spacing.sm }}
    >
      <View style={[styles.table, { alignSelf: "flex-start" }]}>
        {children}
      </View>
    </ScrollView>
  ),
};

export const MarkdownText: React.FC<MarkdownTextProps> = ({
  text,
  baseStyle,
}) => {
  const processed = text.replace(/\\n/g, "\n");
  return (
    <View style={[{ minHeight: 1, flexGrow: 1 }, baseStyle]}>
      <Markdown
        style={styles}
        markdownit={MarkdownIt({ typographer: true })}
        rules={tableRules}
      >
        {processed}
      </Markdown>
    </View>
  );
};

const code = {
  fontFamily: "monospace",
  backgroundColor: "rgba(0,0,0,0.04)",
  borderRadius: borderRadius.sm,
};

const textBase = {
  fontSize: 15,
  color: colors.textSecondary,
  lineHeight: 26,
};

const styles = {
  heading1: {
    fontSize: 22,
    fontWeight: "800" as const,
    color: colors.text,
    marginTop: 0,
    marginBottom: 20,
    letterSpacing: -0.3,
  },
  heading2: {
    fontSize: 17,
    fontWeight: "700" as const,
    color: colors.text,
    marginTop: 28,
    marginBottom: 12,
    letterSpacing: -0.2,
  },
  heading3: {
    fontSize: 15,
    fontWeight: "600" as const,
    color: colors.textSecondary,
    marginTop: 16,
    marginBottom: 8,
  },
  heading4: {
    fontSize: 15,
    fontWeight: "600" as const,
    color: colors.text,
    marginTop: 12,
    marginBottom: 6,
  },
  paragraph: { ...textBase, marginBottom: 12 },
  bullet_list: { marginLeft: 4, marginVertical: 8 },
  ordered_list: { marginLeft: 4, marginVertical: 8 },
  bullet_list_icon: {
    ...textBase,
    color: colors.textTertiary,
    fontSize: 7,
    lineHeight: 26,
    marginRight: 12,
    marginLeft: 4,
  },
  ordered_list_icon: {
    color: colors.textTertiary,
    fontSize: 14,
    fontWeight: "600" as const,
    lineHeight: 26,
    marginRight: 10,
    minWidth: 20,
  },
  list_item: {
    ...textBase,
    flexDirection: "row" as const,
    flexWrap: "wrap" as const,
    marginVertical: 4,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.textTertiary,
    paddingLeft: spacing.md,
    marginVertical: 12,
    backgroundColor: colors.surfaceMuted,
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  code_inline: { ...code, paddingHorizontal: 4, fontSize: 14 },
  code_block: { ...code, padding: spacing.md, fontSize: 14 },
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
  },
  thead: { backgroundColor: colors.surfaceMuted },
  th: {
    fontSize: 13,
    fontWeight: "700" as const,
    color: colors.text,
    padding: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    minWidth: 85,
    flexShrink: 0,
  },
  tr: {
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    flexDirection: "row" as const,
  },
  td: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 20,
    padding: spacing.sm,
    minWidth: 85,
    flexShrink: 0,
  },
  strong: { fontWeight: "700" as const, color: colors.text },
  em: { fontStyle: "italic" as const },
  link: { color: colors.primary, textDecorationLine: "underline" as const },
  hr: {
    backgroundColor: colors.divider,
    height: 1,
    marginVertical: 20,
  },
};
