import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {colors} from '../theme/colors';
import {spacing, fontSize, borderRadius} from '../theme/spacing';

interface MarkdownTextProps {
  text: string;
  baseStyle?: object;
}

const parseInline = (text: string): React.ReactNode[] => {
  const nodes: React.ReactNode[] = [];
  let remaining = text;

  const patterns = [
    {
      regex: /\*\*\*(.+?)\*\*\*/g,
      style: {fontWeight: '700', fontStyle: 'italic'},
    },
    {
      regex: /\*\*(.+?)\*\*/g,
      style: {fontWeight: '700'},
    },
    {
      regex: /\*(.+?)\*/g,
      style: {fontStyle: 'italic'},
    },
    {
      regex: /`(.+?)`/g,
      style: {
        fontFamily: 'monospace',
        backgroundColor: 'rgba(0,0,0,0.05)',
        borderRadius: borderRadius.sm,
        paddingHorizontal: 4,
      },
    },
  ];

  // Simple approach: process sequentially
  let key = 0;
  while (remaining.length > 0) {
    let earliestMatch: {index: number; length: number; text: string; style: object} | null = null;

    for (const p of patterns) {
      p.regex.lastIndex = 0;
      const m = p.regex.exec(remaining);
      if (m && m.index !== undefined) {
        if (!earliestMatch || m.index < earliestMatch.index) {
          earliestMatch = {index: m.index, length: m[0].length, text: m[1], style: p.style};
        }
      }
    }

    if (earliestMatch && earliestMatch.index < remaining.length) {
      if (earliestMatch.index > 0) {
        nodes.push(<Text key={key++}>{remaining.slice(0, earliestMatch.index)}</Text>);
      }
      nodes.push(
        <Text key={key++} style={earliestMatch.style}>
          {earliestMatch.text}
        </Text>,
      );
      remaining = remaining.slice(earliestMatch.index + earliestMatch.length);
    } else {
      nodes.push(<Text key={key++}>{remaining}</Text>);
      break;
    }
  }

  return nodes;
};

const isDivider = (line: string) => /^\s*[-=*]{3,}\s*$/.test(line);

const isHeading = (line: string) => /^#{1,4}\s+/.test(line);

const isBullet = (line: string) => /^\s*[-*]\s+/.test(line);

const isNumbered = (line: string) => /^\s*\d+\.\s+/.test(line);

const isQuote = (line: string) => /^\s*>\s*/.test(line);

const parseHeadingLevel = (line: string): number => {
  const m = line.match(/^(#{1,4})/);
  return m ? m[1].length : 1;
};

const stripHeading = (line: string): string => line.replace(/^#{1,4}\s+/, '');

const stripBullet = (line: string): string => line.replace(/^\s*[-*]\s+/, '');

const stripNumbered = (line: string): string => line.replace(/^\s*\d+\.\s+/, '');

const stripQuote = (line: string): string => line.replace(/^\s*>\s*/, '');

export const MarkdownText: React.FC<MarkdownTextProps> = ({text, baseStyle}) => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let key = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.trim() === '') {
      elements.push(<View key={key++} style={styles.emptyLine} />);
      continue;
    }

    if (isDivider(line)) {
      elements.push(<View key={key++} style={styles.divider} />);
      continue;
    }

    if (isHeading(line)) {
      const level = parseHeadingLevel(line);
      const content = stripHeading(line);
      const headingStyle =
        level === 1
          ? styles.h1
          : level === 2
            ? styles.h2
            : level === 3
              ? styles.h3
              : styles.h4;
      elements.push(
        <Text key={key++} style={[headingStyle, baseStyle]}>
          {parseInline(content)}
        </Text>,
      );
      continue;
    }

    if (isBullet(line)) {
      const content = stripBullet(line);
      elements.push(
        <View key={key++} style={styles.bulletRow}>
          <Text style={styles.bulletDot}>•</Text>
          <Text style={[styles.bulletText, baseStyle]}>{parseInline(content)}</Text>
        </View>,
      );
      continue;
    }

    if (isNumbered(line)) {
      const content = stripNumbered(line);
      const numMatch = line.match(/^\s*(\d+)\.\s+/);
      const num = numMatch ? numMatch[1] : '1';
      elements.push(
        <View key={key++} style={styles.bulletRow}>
          <Text style={styles.numberBadge}>{num}.</Text>
          <Text style={[styles.bulletText, baseStyle]}>{parseInline(content)}</Text>
        </View>,
      );
      continue;
    }

    if (isQuote(line)) {
      const content = stripQuote(line);
      elements.push(
        <View key={key++} style={styles.quoteBox}>
          <Text style={[styles.quoteText, baseStyle]}>{parseInline(content)}</Text>
        </View>,
      );
      continue;
    }

    elements.push(
      <Text key={key++} style={[styles.paragraph, baseStyle]}>
        {parseInline(line)}
      </Text>,
    );
  }

  return <View>{elements}</View>;
};

const styles = StyleSheet.create({
  emptyLine: {
    height: spacing.sm,
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.sm,
  },
  h1: {
    fontSize: fontSize.lg,
    fontWeight: '800',
    color: colors.text,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  h2: {
    fontSize: fontSize.md,
    fontWeight: '700',
    color: colors.text,
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  h3: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  h4: {
    fontSize: fontSize.md,
    fontWeight: '600',
    color: colors.text,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  paragraph: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginVertical: 2,
    paddingLeft: spacing.sm,
  },
  bulletDot: {
    fontSize: fontSize.md,
    color: colors.primary,
    marginRight: spacing.sm,
    lineHeight: 22,
  },
  numberBadge: {
    fontSize: fontSize.sm,
    color: colors.primary,
    fontWeight: '700',
    marginRight: spacing.sm,
    lineHeight: 22,
    minWidth: 20,
  },
  bulletText: {
    fontSize: fontSize.md,
    color: colors.text,
    lineHeight: 22,
    flex: 1,
  },
  quoteBox: {
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    paddingLeft: spacing.md,
    marginVertical: spacing.xs,
    backgroundColor: colors.primaryMuted,
    paddingVertical: spacing.sm,
    paddingRight: spacing.sm,
    borderRadius: borderRadius.sm,
  },
  quoteText: {
    fontSize: fontSize.md,
    color: colors.textSecondary,
    fontStyle: 'italic',
    lineHeight: 22,
  },
});
