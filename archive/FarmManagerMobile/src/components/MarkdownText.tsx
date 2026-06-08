import React from "react";
import Markdown, { MarkdownIt } from "react-native-markdown-display";
import { View, ScrollView } from "react-native";
import { colors } from "../theme/colors";
import { spacing, borderRadius } from "../theme/spacing";

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
      style={{ marginVertical: spacing.sm, maxWidth: "100%" }}
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
  backgroundColor: "rgba(15, 23, 42, 0.05)",
  borderRadius: borderRadius.sm,
};

const textBase = {
  fontSize: 15,
  color: colors.textSecondary,
  lineHeight: 24,
};

const styles = {
  heading1: {
    fontSize: 19,
    fontWeight: "700" as const,
    color: colors.text,
    marginTop: 0,
    marginBottom: 12,
  },
  heading2: {
    fontSize: 16,
    fontWeight: "700" as const,
    color: colors.text,
    marginTop: 18,
    marginBottom: 8,
  },
  heading3: {
    fontSize: 15,
    fontWeight: "600" as const,
    color: colors.text,
    marginTop: 14,
    marginBottom: 6,
  },
  heading4: {
    fontSize: 15,
    fontWeight: "600" as const,
    color: colors.text,
    marginTop: 12,
    marginBottom: 6,
  },
  paragraph: { ...textBase, marginBottom: 8 },
  bullet_list: { marginLeft: 0, marginVertical: 6 },
  ordered_list: { marginLeft: 0, marginVertical: 6 },
  bullet_list_icon: {
    ...textBase,
    color: colors.success,
    fontSize: 7,
    lineHeight: 24,
    marginRight: 10,
    marginLeft: 2,
  },
  ordered_list_icon: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: "600" as const,
    lineHeight: 24,
    marginRight: 8,
    minWidth: 22,
  },
  list_item: {
    ...textBase,
    flexDirection: "row" as const,
    flexWrap: "wrap" as const,
    marginVertical: 2,
  },
  blockquote: {
    borderLeftWidth: 3,
    borderLeftColor: colors.success,
    paddingLeft: spacing.sm,
    marginVertical: 8,
    backgroundColor: colors.successMuted,
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  code_inline: { ...code, paddingHorizontal: 4, fontSize: 13 },
  code_block: { ...code, padding: spacing.md, fontSize: 13 },
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: borderRadius.sm,
  },
  thead: { backgroundColor: colors.surfaceMuted },
  th: {
    fontSize: 12,
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
    fontSize: 12,
    color: colors.textSecondary,
    lineHeight: 18,
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
