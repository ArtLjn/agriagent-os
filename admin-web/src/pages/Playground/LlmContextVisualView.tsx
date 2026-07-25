import { useState } from 'react';
import type { ReactNode } from 'react';

import { palette } from '../../styles/theme';
import { formatTracePayload } from '../../utils/tracePayload';
import type { PlaygroundLlmContextSnapshot } from './traceMetrics';

const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const PRE_BG = '#161b22';
const ACCENT = palette.accent;
const PANEL_BORDER = '#30363d';

interface RuntimeContextSection {
  title: string;
  content: string;
}

function formatMetricNumber(value: number | null): string {
  if (value === null) return '-';
  return value.toLocaleString('zh-CN');
}

function stringifyContent(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return formatTracePayload(value);
}

function cleanRuntimeContextPrompt(systemPrompt: string): string {
  return systemPrompt.replace(/<\/?runtime_context>/g, '').trim();
}

function parseRuntimeContextSections(systemPrompt: string): RuntimeContextSection[] {
  const cleaned = cleanRuntimeContextPrompt(systemPrompt);
  if (!cleaned) return [];

  const sections: RuntimeContextSection[] = [];
  const lines = cleaned.split('\n');
  let currentTitle = 'system_prompt';
  let buffer: string[] = [];

  const flush = () => {
    const content = buffer.join('\n').trim();
    if (content) sections.push({ title: currentTitle, content });
    buffer = [];
  };

  for (const line of lines) {
    const heading = line.match(/^###\s+(.+?)\s*$/);
    if (heading) {
      flush();
      currentTitle = heading[1];
      continue;
    }
    buffer.push(line);
  }
  flush();

  return sections;
}

function TracePre({ children, maxHeight }: { children: string; maxHeight: number }) {
  return (
    <pre style={{
      backgroundColor: PRE_BG,
      border: `1px solid ${PANEL_BORDER}`,
      borderRadius: 6,
      color: TEXT,
      fontSize: 12,
      lineHeight: 1.6,
      margin: 0,
      maxHeight,
      overflow: 'auto',
      padding: 10,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
    }}>
      {children}
    </pre>
  );
}

function CollapsibleContextJson({ snapshot }: { snapshot: PlaygroundLlmContextSnapshot }) {
  const [expanded, setExpanded] = useState(false);
  const json = formatTracePayload(snapshot.raw);

  return (
    <section
      aria-label="LLM Context JSON"
      style={{
        border: `1px solid ${BORDER}`,
        borderRadius: 8,
        background: PRE_BG,
        overflow: 'hidden',
      }}
    >
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        style={{
          alignItems: 'center',
          background: 'transparent',
          border: 0,
          color: TEXT,
          cursor: 'pointer',
          display: 'flex',
          fontFamily: 'monospace',
          fontSize: 13,
          gap: 10,
          justifyContent: 'space-between',
          padding: '12px 14px',
          textAlign: 'left',
          width: '100%',
        }}
      >
        <span>final_llm_context.json</span>
        <span style={{ color: TEXT_DIM, fontFamily: 'inherit' }}>
          {expanded ? '收起' : '展开'}
        </span>
      </button>
      {expanded && (
        <div style={{ borderTop: `1px solid ${BORDER}` }}>
          <TracePre maxHeight={680}>{json}</TracePre>
        </div>
      )}
    </section>
  );
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      border: `1px solid ${PANEL_BORDER}`,
      borderRadius: 8,
      background: PRE_BG,
      padding: 12,
      minWidth: 0,
    }}>
      <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>{label}</div>
      <div style={{
        color: TEXT,
        fontFamily: 'monospace',
        fontSize: 18,
        fontWeight: 700,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {value}
      </div>
    </div>
  );
}

function SectionPanel({ title, subtitle, children }: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section style={{
      border: `1px solid ${PANEL_BORDER}`,
      borderRadius: 8,
      background: PRE_BG,
      minWidth: 0,
      overflow: 'hidden',
    }}>
      <div style={{
        borderBottom: `1px solid ${PANEL_BORDER}`,
        padding: '10px 12px',
      }}>
        <div style={{ color: TEXT, fontSize: 14, fontWeight: 700 }}>{title}</div>
        {subtitle && <div style={{ color: TEXT_DIM, fontSize: 12, marginTop: 4 }}>{subtitle}</div>}
      </div>
      <div style={{ padding: 12 }}>{children}</div>
    </section>
  );
}

function ContextBlockList({ snapshot, sections }: {
  snapshot: PlaygroundLlmContextSnapshot;
  sections: RuntimeContextSection[];
}) {
  const sectionTitles = new Set(sections.map((section) => section.title));
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {snapshot.contextBlocks.length > 0 ? snapshot.contextBlocks.map((block) => {
        const visible = sectionTitles.has(block);
        return (
          <div
            key={block}
            style={{
              alignItems: 'center',
              border: `1px solid ${visible ? 'rgba(88,166,255,0.45)' : PANEL_BORDER}`,
              borderRadius: 6,
              display: 'flex',
              gap: 8,
              justifyContent: 'space-between',
              padding: '8px 10px',
            }}
          >
            <span style={{ color: TEXT, fontFamily: 'monospace', fontSize: 13 }}>{block}</span>
            <span style={{ color: visible ? ACCENT : TEXT_DIM, fontSize: 12 }}>
              {visible ? '已注入' : '仅元数据'}
            </span>
          </div>
        );
      }) : (
        <div style={{ color: TEXT_DIM, fontSize: 13 }}>本轮 trace 未记录 context_blocks。</div>
      )}
    </div>
  );
}

function RuntimeContextSections({ sections }: { sections: RuntimeContextSection[] }) {
  if (sections.length === 0) {
    return <div style={{ color: TEXT_DIM, fontSize: 13 }}>本轮 trace 未记录 system_prompt 上下文。</div>;
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {sections.map((section) => (
        <article
          key={section.title}
          style={{
            border: `1px solid ${PANEL_BORDER}`,
            borderRadius: 6,
            overflow: 'hidden',
          }}
        >
          <div style={{
            background: '#0d1117',
            borderBottom: `1px solid ${PANEL_BORDER}`,
            color: ACCENT,
            fontFamily: 'monospace',
            fontSize: 13,
            fontWeight: 700,
            padding: '8px 10px',
          }}>
            {section.title}
          </div>
          <div style={{
            color: TEXT,
            fontSize: 13,
            lineHeight: 1.75,
            maxHeight: 180,
            overflow: 'auto',
            padding: '10px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {section.content}
          </div>
        </article>
      ))}
    </div>
  );
}

function MessageTimeline({ snapshot }: { snapshot: PlaygroundLlmContextSnapshot }) {
  if (snapshot.messages.length === 0) {
    return <div style={{ color: TEXT_DIM, fontSize: 13 }}>本轮 trace 未记录 messages。</div>;
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {snapshot.messages.map((message) => (
        <article
          key={`${message.index}-${message.role}-${message.name ?? ''}`}
          style={{
            border: `1px solid ${PANEL_BORDER}`,
            borderRadius: 6,
            padding: 10,
          }}
        >
          <div style={{ alignItems: 'center', display: 'flex', gap: 8, marginBottom: 8 }}>
            <span style={{
              background: message.role === 'tool' ? 'rgba(63,185,80,0.16)' : 'rgba(88,166,255,0.14)',
              border: `1px solid ${message.role === 'tool' ? '#3fb950' : ACCENT}`,
              borderRadius: 999,
              color: message.role === 'tool' ? '#7ee787' : ACCENT,
              fontFamily: 'monospace',
              fontSize: 12,
              padding: '2px 8px',
            }}>
              {message.role}
            </span>
            <span style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
              #{message.index} · {message.type}
              {message.name ? ` · ${message.name}` : ''}
            </span>
          </div>
          <div style={{
            color: TEXT,
            fontSize: 13,
            lineHeight: 1.7,
            maxHeight: 120,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {stringifyContent(message.content) || '-'}
          </div>
        </article>
      ))}
    </div>
  );
}

export function LlmContextVisualView({ snapshot }: { snapshot: PlaygroundLlmContextSnapshot }) {
  const sections = parseRuntimeContextSections(snapshot.systemPrompt);
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{
        display: 'grid',
        gap: 10,
        gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
      }}>
        <MetricTile label="Context Blocks" value={formatMetricNumber(snapshot.contextBlocks.length)} />
        <MetricTile label="Messages" value={formatMetricNumber(snapshot.messages.length)} />
        <MetricTile label="Prompt Token" value={formatMetricNumber(snapshot.promptTokens)} />
        <MetricTile label="Token Budget" value={formatMetricNumber(snapshot.maxTokens)} />
      </div>
      <div style={{
        display: 'grid',
        gap: 14,
        gridTemplateColumns: 'minmax(240px, 0.8fr) minmax(320px, 1.2fr)',
      }}>
        <SectionPanel title="Context Blocks" subtitle="本轮被选中并注入模型的上下文源">
          <ContextBlockList snapshot={snapshot} sections={sections} />
        </SectionPanel>
        <SectionPanel title="Runtime Context" subtitle="system prompt 中可读的上下文分区">
          <RuntimeContextSections sections={sections} />
        </SectionPanel>
      </div>
      <SectionPanel title="Messages" subtitle="最终送入 LLM 的消息序列">
        <MessageTimeline snapshot={snapshot} />
      </SectionPanel>
      <SectionPanel title="原始快照 JSON" subtitle="完整 trace payload，默认折叠在底部">
        <CollapsibleContextJson snapshot={snapshot} />
      </SectionPanel>
    </div>
  );
}
