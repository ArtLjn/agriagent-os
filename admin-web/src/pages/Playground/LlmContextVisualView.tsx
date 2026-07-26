import { useState } from 'react';
import type { ReactNode } from 'react';

import { palette } from '../../styles/theme';
import { formatTracePayload } from '../../utils/tracePayload';
import type {
  PlaygroundLlmContextBlockDetail,
  PlaygroundLlmContextSnapshot,
} from './traceMetrics';

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

function formatDetailNumber(value: number | null): string {
  return value === null ? '-' : value.toLocaleString('zh-CN');
}

function groupBlocksByCategory(
  blocks: PlaygroundLlmContextBlockDetail[],
): Array<[string, PlaygroundLlmContextBlockDetail[]]> {
  const grouped = new Map<string, PlaygroundLlmContextBlockDetail[]>();
  for (const block of blocks) {
    const category = block.category || 'uncategorized';
    grouped.set(category, [...(grouped.get(category) ?? []), block]);
  }
  return Array.from(grouped.entries());
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

function DetailChip({ label, value, accent }: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <span style={{
      border: `1px solid ${accent ? 'rgba(88,166,255,0.45)' : PANEL_BORDER}`,
      borderRadius: 999,
      color: accent ? ACCENT : TEXT_DIM,
      fontFamily: 'monospace',
      fontSize: 12,
      padding: '2px 7px',
      whiteSpace: 'nowrap',
    }}>
      {label}: {value}
    </span>
  );
}

function ContextBlockList({ snapshot, sections }: {
  snapshot: PlaygroundLlmContextSnapshot;
  sections: RuntimeContextSection[];
}) {
  if (snapshot.contextBlockDetails.length > 0) {
    return (
      <div style={{ display: 'grid', gap: 12 }}>
        {groupBlocksByCategory(snapshot.contextBlockDetails).map(([category, blocks]) => (
          <div key={category} style={{ display: 'grid', gap: 8 }}>
            <div style={{
              color: ACCENT,
              fontFamily: 'monospace',
              fontSize: 12,
              fontWeight: 700,
            }}>
              category: {category}
            </div>
            {blocks.map((block) => (
              <article
                key={`${category}-${block.key}`}
                style={{
                  border: `1px solid ${block.dropped ? 'rgba(248,81,73,0.45)' : PANEL_BORDER}`,
                  borderRadius: 6,
                  display: 'grid',
                  gap: 8,
                  padding: '8px 10px',
                }}
              >
                <div style={{
                  alignItems: 'center',
                  display: 'flex',
                  gap: 8,
                  justifyContent: 'space-between',
                }}>
                  <span style={{ color: TEXT, fontFamily: 'monospace', fontSize: 13 }}>
                    {block.key}
                  </span>
                  <span style={{
                    color: block.decision === 'selected' ? '#7ee787' : TEXT_DIM,
                    fontFamily: 'monospace',
                    fontSize: 12,
                  }}>
                    {block.decision || '-'}
                  </span>
                </div>
                <div style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 6,
                }}>
                  <DetailChip label="source" value={block.source || '-'} />
                  <DetailChip label="compressed" value={block.compressed ? 'true' : 'false'} />
                  <DetailChip label="dropped" value={block.dropped ? 'true' : 'false'} />
                  <DetailChip label="required" value={block.required ? 'true' : 'false'} />
                  <DetailChip label="token" value={formatDetailNumber(block.tokenEstimate)} accent />
                  <DetailChip label="priority" value={formatDetailNumber(block.priority)} />
                </div>
                <div style={{ color: TEXT_DIM, fontSize: 12, lineHeight: 1.6 }}>
                  reason: {block.reason || '-'}
                </div>
              </article>
            ))}
          </div>
        ))}
      </div>
    );
  }

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

function RuntimeContextSections({
  snapshot,
  sections,
}: {
  snapshot: PlaygroundLlmContextSnapshot;
  sections: RuntimeContextSection[];
}) {
  if (snapshot.runtimeSections.length > 0) {
    return (
      <div style={{ display: 'grid', gap: 10 }}>
        {snapshot.runtimeSections.map((section) => (
          <article
            key={section.name}
            style={{
              border: `1px solid ${PANEL_BORDER}`,
              borderRadius: 6,
              overflow: 'hidden',
            }}
          >
            <div style={{
              alignItems: 'center',
              background: '#0d1117',
              borderBottom: `1px solid ${PANEL_BORDER}`,
              display: 'flex',
              gap: 8,
              justifyContent: 'space-between',
              padding: '8px 10px',
            }}>
              <span style={{
                color: ACCENT,
                fontFamily: 'monospace',
                fontSize: 13,
                fontWeight: 700,
              }}>
                {section.name}
              </span>
              <span style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
                token: {formatDetailNumber(section.tokenEstimate)}
              </span>
            </div>
            <div style={{ display: 'grid', gap: 10, padding: 10 }}>
              {section.blocks.length > 0 ? section.blocks.map((block) => {
                const content = block.content || block.contentPreview;
                return (
                  <div key={block.key} style={{ display: 'grid', gap: 6 }}>
                    <div style={{ color: TEXT_DIM, fontFamily: 'monospace', fontSize: 12 }}>
                      {block.key}
                    </div>
                    <div style={{
                      color: TEXT,
                      fontSize: 13,
                      lineHeight: 1.75,
                      maxHeight: 180,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}>
                      {content || '-'}
                    </div>
                  </div>
                );
              }) : (
                <div style={{ color: TEXT_DIM, fontSize: 13 }}>该分区未记录上下文 block。</div>
              )}
            </div>
          </article>
        ))}
      </div>
    );
  }

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
            {message.compressed && (
              <span style={{
                border: '1px solid rgba(250,173,20,0.5)',
                borderRadius: 999,
                color: '#faad14',
                fontSize: 12,
                padding: '2px 8px',
              }}>
                已压缩
              </span>
            )}
          </div>
          {message.role === 'tool' && (
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              marginBottom: 8,
            }}>
              <DetailChip label="tool_call_id" value={message.tool_call_id ?? '-'} />
              <DetailChip label="name" value={message.name ?? '-'} />
              <DetailChip label="status" value={message.status ?? '-'} />
            </div>
          )}
          <div style={{
            color: TEXT,
            fontSize: 13,
            lineHeight: 1.7,
            maxHeight: 120,
            overflow: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}>
            {stringifyContent(message.content) || message.contentPreview || '-'}
          </div>
        </article>
      ))}
    </div>
  );
}

export function LlmContextVisualView({ snapshot }: { snapshot: PlaygroundLlmContextSnapshot }) {
  const sections = snapshot.runtimeSections.length > 0
    ? []
    : parseRuntimeContextSections(snapshot.systemPrompt);
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
          <RuntimeContextSections snapshot={snapshot} sections={sections} />
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
