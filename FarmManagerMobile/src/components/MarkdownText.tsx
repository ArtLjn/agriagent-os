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

const h = (size: number, weight: string, color: string) => ({
  fontSize: size,
  fontWeight: weight as
    | "normal"
    | "bold"
    | "100"
    | "200"
    | "300"
    | "400"
    | "500"
    | "600"
    | "700"
    | "800"
    | "900",
  color,
  marginTop: spacing.sm,
  marginBottom: spacing.xs,
});

const code = {
  fontFamily: "monospace",
  backgroundColor: "rgba(0,0,0,0.05)",
  borderRadius: borderRadius.sm,
};

const textBase = {
  fontSize: fontSize.md,
  color: colors.text,
  lineHeight: 22,
};

const styles = {
  heading1: h(fontSize.lg, "800", colors.text),
  heading2: h(fontSize.md, "700", colors.text),
  heading3: h(fontSize.md, "600", colors.textSecondary),
  heading4: h(fontSize.md, "600", colors.text),
  paragraph: { ...textBase, marginBottom: spacing.xs },
  bullet_list: { marginLeft: spacing.sm, marginVertical: spacing.xs },
  ordered_list: { marginLeft: spacing.sm, marginVertical: spacing.xs },
  bullet_list_icon: {
    ...textBase,
    color: colors.primary,
    marginRight: spacing.sm,
  },
  ordered_list_icon: {
    color: colors.primary,
    fontSize: fontSize.sm,
    fontWeight: "700" as const,
    lineHeight: 22,
    marginRight: spacing.sm,
    minWidth: 20,
  },
  list_item: {
    ...textBase,
    flexDirection: "row" as const,
    flexWrap: "wrap" as const,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    paddingLeft: spacing.md,
    marginVertical: spacing.xs,
    backgroundColor: colors.primaryMuted,
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  code_inline: { ...code, paddingHorizontal: 4, fontSize: fontSize.sm },
  code_block: { ...code, padding: spacing.sm, fontSize: fontSize.sm },
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
  },
  thead: { backgroundColor: colors.primaryMuted },
  th: {
    fontSize: fontSize.xs,
    fontWeight: "700" as const,
    color: colors.text,
    padding: spacing.xs,
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
    fontSize: fontSize.xs,
    color: colors.text,
    lineHeight: 18,
    padding: spacing.xs,
    minWidth: 85,
    flexShrink: 0,
  },
  strong: { fontWeight: "700" as const },
  em: { fontStyle: "italic" as const },
  link: { color: colors.primary, textDecorationLine: "underline" as const },
  hr: { backgroundColor: colors.border, height: 1, marginVertical: spacing.sm },
};
