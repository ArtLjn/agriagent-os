import type { CSSProperties, ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { normalizeAssistantMarkdown } from './MarkdownContentModel';

function TableWrapper({ children }: { children?: ReactNode }) {
  return (
    <div style={{ overflowX: 'auto', maxWidth: '100%', margin: '10px 0' }}>
      <table style={{ borderCollapse: 'collapse', minWidth: '100%' }}>{children}</table>
    </div>
  );
}

function TableCell({ children, header = false }: { children?: ReactNode; header?: boolean }) {
  const Tag = header ? 'th' : 'td';
  return (
    <Tag style={{
      border: '1px solid rgba(139,148,158,0.32)',
      padding: '6px 8px',
      textAlign: 'left',
      verticalAlign: 'top',
      whiteSpace: 'normal',
    }}>
      {children}
    </Tag>
  );
}

export function MarkdownContent({ content, style }: { content: string; style?: CSSProperties }) {
  return (
    <div style={style}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => <TableWrapper>{children}</TableWrapper>,
          th: ({ children }) => <TableCell header>{children}</TableCell>,
          td: ({ children }) => <TableCell>{children}</TableCell>,
        }}
      >
        {normalizeAssistantMarkdown(content)}
      </ReactMarkdown>
    </div>
  );
}
