const HTML_BREAK_RE = /<br\s*\/?>/gi;
const GLUED_TABLE_ROW_RE = /\s*\|\|\s*/;

export function normalizeAssistantMarkdown(content: string): string {
  const repairedRows = content.split('\n').flatMap((line) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith('|') || !trimmed.includes('||')) return [line];

    return trimmed.split(GLUED_TABLE_ROW_RE).map((part) => normalizeTableRow(part));
  });

  return repairedRows
    .map((line) => (
      isMarkdownTableRow(line)
        ? line.replace(HTML_BREAK_RE, '；')
        : line.replace(HTML_BREAK_RE, '\n')
    ))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n');
}

function normalizeTableRow(row: string): string {
  let normalized = row.trim().replace(HTML_BREAK_RE, '；');
  if (!normalized.startsWith('|')) normalized = `| ${normalized}`;
  if (!normalized.endsWith('|')) normalized = `${normalized} |`;
  return normalized;
}

function isMarkdownTableRow(line: string): boolean {
  return /^\s*\|.*\|\s*$/.test(line);
}
