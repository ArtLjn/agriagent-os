import { useState, useMemo } from 'react';
import type { GanttNode, GanttTimelineProps } from './types';
import { getNodeColor } from '../../constants/trace';

const BG = '#0d1117';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const BAR_HEIGHT = 20;

/* ── 统计信息条 ── */
function StatsBar({
  totalNodes,
  totalRounds,
  success,
  error,
}: {
  totalNodes: number;
  totalRounds: number;
  success: number;
  error: number;
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 32,
        padding: '12px 16px',
        borderBottom: `1px solid ${BORDER}`,
        fontSize: 13,
      }}
    >
      <span style={{ color: TEXT_DIM }}>
        总节点数: <strong style={{ color: TEXT }}>{totalNodes}</strong>
      </span>
      <span style={{ color: TEXT_DIM }}>
        总轮次: <strong style={{ color: TEXT }}>{totalRounds}</strong>
      </span>
      <span style={{ color: TEXT_DIM }}>
        成功: <strong style={{ color: '#52c41a' }}>{success}</strong>
      </span>
      <span style={{ color: TEXT_DIM }}>
        失败: <strong style={{ color: '#ff4d4f' }}>{error}</strong>
      </span>
    </div>
  );
}

/* ── 表头 ── */
function TimelineHeader() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '10px 16px',
        borderBottom: `2px solid ${BORDER}`,
        fontSize: 13,
        fontWeight: 600,
        color: TEXT_DIM,
      }}
    >
      <div style={{ width: 40, textAlign: 'center' }}>类型</div>
      <div style={{ width: 220, paddingLeft: 8 }}>名称</div>
      <div style={{ width: 120 }}>开始时间</div>
      <div style={{ width: 80 }}>耗时</div>
      <div style={{ width: 80 }}>状态</div>
      <div style={{ flex: 1 }}>时间线</div>
    </div>
  );
}

/* ── 轮次分隔线（可点击展开/收起） ── */
function RoundDivider({
  roundIndex,
  recordId,
  nodeCount,
  roundDuration,
  successCount,
  errorCount,
  isExpanded,
  onToggle,
}: {
  roundIndex: number;
  recordId: string;
  nodeCount: number;
  roundDuration: number;
  successCount: number;
  errorCount: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '12px 16px',
        margin: '8px 0',
        borderTop: `2px solid ${BORDER}`,
        borderBottom: `1px solid ${BORDER}`,
        background: isExpanded ? '#1a2332' : 'transparent',
        cursor: 'pointer',
        transition: 'background 0.2s',
      }}
    >
      <span
        style={{
          display: 'inline-block',
          padding: '4px 12px',
          background: isExpanded ? '#2980b9' : '#3498db',
          color: '#fff',
          borderRadius: 15,
          fontSize: 12,
          fontWeight: 600,
          marginRight: 15,
        }}
      >
        第 {roundIndex + 1} 轮
      </span>
      <span
        style={{
          fontSize: 12,
          color: TEXT_DIM,
          fontFamily: 'monospace',
          marginRight: 16,
        }}
      >
        requestId: {recordId}
      </span>
      <span style={{ marginLeft: 'auto', fontSize: 12, color: TEXT_DIM }}>
        {nodeCount} 节点 | {roundDuration}ms | ✓{successCount} ✗{errorCount}
      </span>
      <span style={{ marginLeft: 10, fontSize: 11, color: '#8b949e' }}>
        {isExpanded ? '点击收起 ▲' : '点击展开 ▼'}
      </span>
    </div>
  );
}

/* ── 收起时的紧凑汇总条 ── */
function CompactRoundBar({ nodes }: { nodes: GanttNode[] }) {
  const segments = useMemo(() => {
    const valid = nodes.filter((n) => n.duration_ms !== null && n.duration_ms > 0);
    if (valid.length === 0) return [];

    const totalDur = valid.reduce((s, n) => s + (n.duration_ms || 0), 0);
    let offset = 0;
    return valid.map((n) => {
      const left = (offset / totalDur) * 100;
      const width = Math.max(((n.duration_ms || 0) / totalDur) * 100, 0.3);
      offset += n.duration_ms || 0;
      return { left, width, color: getNodeColor(n.node_type) };
    });
  }, [nodes]);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 16px',
        height: 36,
      }}
    >
      <div
        style={{
          width: 520,
          textAlign: 'right',
          paddingRight: 15,
          fontSize: 12,
          color: '#3498db',
        }}
      >
        点击查看详情 →
      </div>
      <div
        style={{
          flex: 1,
          height: 20,
          position: 'relative',
          background: '#21262d',
          borderRadius: 4,
          marginRight: 10,
        }}
      >
        {segments.map((seg, i) => (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: `${seg.left}%`,
              width: `${seg.width}%`,
              height: '100%',
              background: seg.color,
              borderRadius: 4,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/* ── 展开时的汇总时间线 ── */
function RoundSummaryBar({ nodes }: { nodes: GanttNode[] }) {
  const totalDur = nodes.reduce((s, n) => s + (n.duration_ms || 0), 0);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 16px',
        height: 36,
        background: '#161b22',
        borderBottom: `1px solid ${BORDER}`,
      }}
    >
      <div
        style={{
          width: 520,
          textAlign: 'right',
          paddingRight: 15,
          fontSize: 12,
          color: TEXT_DIM,
        }}
      >
        该轮总耗时:
      </div>
      <div
        style={{
          flex: 1,
          height: 20,
          position: 'relative',
          background: '#21262d',
          borderRadius: 4,
          marginRight: 10,
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            width: '100%',
            height: '100%',
            background: '#3498db',
            borderRadius: 4,
          }}
        />
      </div>
      <div style={{ fontSize: 11, color: TEXT_DIM, minWidth: 60 }}>{totalDur}ms</div>
    </div>
  );
}

/* ── 节点信息行 ── */
function NodeRow({
  node,
  onClick,
}: {
  node: GanttNode;
  onClick?: () => void;
}) {
  const color = getNodeColor(node.node_type);
  const startTime = node.start_time
    ? new Date(node.start_time).toLocaleTimeString('zh-CN')
    : '-';

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 16px',
        borderBottom: `1px solid ${BORDER}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = '#1a2332';
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = 'transparent';
      }}
    >
      {/* 类型圆点 */}
      <div style={{ width: 40, textAlign: 'center' }}>
        <span
          style={{
            display: 'inline-block',
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: color,
          }}
        />
      </div>

      {/* 名称 */}
      <div
        style={{
          width: 220,
          paddingLeft: 8,
          paddingRight: 10,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          color: TEXT,
          fontSize: 13,
        }}
        title={node.node_name}
      >
        {node.node_name}
      </div>

      {/* 开始时间 */}
      <div style={{ width: 120, fontSize: 12, color: TEXT_DIM }}>{startTime}</div>

      {/* 耗时 */}
      <div style={{ width: 80, fontSize: 12, color: TEXT_DIM }}>
        {node.duration_ms ?? '-'}ms
      </div>

      {/* 状态 */}
      <div style={{ width: 80 }}>
        <span
          style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: 10,
            fontSize: 11,
            fontWeight: 500,
            background: node.status === 'success' ? '#1a3a1a' : '#3a1a1a',
            color: node.status === 'success' ? '#52c41a' : '#ff4d4f',
          }}
        >
          {node.status}
        </span>
      </div>

      {/* 时间线条形图 */}
      <div style={{ flex: 1, height: BAR_HEIGHT, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            width: '100%',
            height: '100%',
            background: '#21262d',
            borderRadius: 4,
          }}
        />
        {node.duration_ms && node.duration_ms > 0 && (
          <div
            style={{
              position: 'absolute',
              left: 0,
              width: '100%',
              height: '100%',
              background: color,
              borderRadius: 4,
              opacity: 0.85,
            }}
            title={`${node.node_name}: ${node.duration_ms}ms`}
          />
        )}
      </div>
    </div>
  );
}

/* ── 图例 ── */
function Legend() {
  const items = [
    { type: 'routing', label: '路由决策' },
    { type: 'prompt_render', label: 'Prompt 渲染' },
    { type: 'llm_call', label: 'LLM 调用' },
    { type: 'skill_call', label: 'Skill 执行' },
    { type: 'error', label: '错误' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        gap: 20,
        marginTop: 16,
        flexWrap: 'wrap',
        padding: '0 16px',
      }}
    >
      {items.map(({ type, label }) => (
        <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div
            style={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: getNodeColor(type),
            }}
          />
          <span style={{ color: TEXT_DIM, fontSize: 12 }}>{label}</span>
        </div>
      ))}
    </div>
  );
}

/* ── 主组件 ── */
export function GanttTimeline({ rounds, onNodeClick }: GanttTimelineProps) {
  const [expandedRounds, setExpandedRounds] = useState<Set<number>>(new Set());

  const toggleRound = (roundIndex: number) => {
    setExpandedRounds((prev) => {
      const next = new Set(prev);
      if (next.has(roundIndex)) {
        next.delete(roundIndex);
      } else {
        next.add(roundIndex);
      }
      return next;
    });
  };

  const stats = useMemo(() => {
    let totalNodes = 0;
    let success = 0;
    let error = 0;
    for (const round of rounds) {
      totalNodes += round.nodes.length;
      for (const node of round.nodes) {
        if (node.status === 'success') success++;
        else if (node.status === 'error') error++;
      }
    }
    return {
      totalNodes,
      totalRounds: rounds.length,
      success,
      error,
    };
  }, [rounds]);

  if (!rounds || rounds.length === 0) {
    return (
      <div
        style={{
          background: BG,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
          padding: 32,
          color: TEXT_DIM,
          textAlign: 'center',
        }}
      >
        暂无执行链路数据
      </div>
    );
  }

  return (
    <div
      style={{
        background: BG,
        border: `1px solid ${BORDER}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <StatsBar {...stats} />
      <TimelineHeader />

      {rounds.map((round, rIdx) => {
        const isExpanded = expandedRounds.has(rIdx);
        const roundDur = round.nodes.reduce((s, n) => s + (n.duration_ms || 0), 0);
        const successCount = round.nodes.filter((n) => n.status === 'success').length;
        const errorCount = round.nodes.filter((n) => n.status === 'error').length;

        return (
          <div key={rIdx}>
            <RoundDivider
              roundIndex={rIdx}
              recordId=""
              nodeCount={round.nodes.length}
              roundDuration={roundDur}
              successCount={successCount}
              errorCount={errorCount}
              isExpanded={isExpanded}
              onToggle={() => toggleRound(rIdx)}
            />

            {isExpanded ? (
              <>
                <RoundSummaryBar nodes={round.nodes} />
                {round.nodes.map((node, nIdx) => (
                  <NodeRow
                    key={nIdx}
                    node={node}
                    onClick={() => onNodeClick?.(rIdx, nIdx, node)}
                  />
                ))}
              </>
            ) : (
              <CompactRoundBar nodes={round.nodes} />
            )}
          </div>
        );
      })}

      <Legend />
    </div>
  );
}

export default GanttTimeline;
