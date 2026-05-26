import { useMemo } from 'react';
import type { GanttNode, GanttRound, GanttTimelineProps } from './types';
import { getNodeColor, getNodeLabel, NODE_TYPE_COLORS } from '../../constants/trace';

const BG = '#0d1117';
const BORDER = '#30363d';
const TEXT_DIM = '#8b949e';
const ROW_HEIGHT = 40;
const BAR_HEIGHT = 24;
const PADDING_LEFT = 80;
const MIN_BAR_WIDTH = 4;
const TIMELINE_WIDTH = 800;

interface PositionedNode extends GanttNode {
  left: number;
  width: number;
}

function calculatePositions(nodes: GanttNode[]): PositionedNode[] {
  const validNodes = nodes.filter(
    (n): n is GanttNode & { duration_ms: number; start_time: string } =>
      n.duration_ms !== null && n.start_time !== null
  );
  if (validNodes.length === 0) return [];

  const starts = validNodes.map((n) => new Date(n.start_time).getTime());
  const minStart = Math.min(...starts);
  const maxEnd = Math.max(
    ...validNodes.map((n) => new Date(n.start_time).getTime() + n.duration_ms)
  );
  const totalDuration = maxEnd - minStart || 1;

  return validNodes.map((node) => {
    const startMs = new Date(node.start_time).getTime();
    const left = ((startMs - minStart) / totalDuration) * TIMELINE_WIDTH;
    const width = Math.max((node.duration_ms / totalDuration) * TIMELINE_WIDTH, MIN_BAR_WIDTH);
    return { ...node, left, width };
  });
}

const RoundRow: React.FC<{
  round: GanttRound;
  roundIndex: number;
  onNodeClick?: (roundIndex: number, nodeIndex: number) => void;
}> = ({ round, roundIndex, onNodeClick }) => {
  const positioned = useMemo(() => calculatePositions(round.nodes), [round.nodes]);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: ROW_HEIGHT,
        borderBottom: `1px solid ${BORDER}`,
        position: 'relative',
      }}
    >
      <div
        style={{
          width: PADDING_LEFT,
          paddingLeft: 12,
          color: TEXT_DIM,
          fontSize: 13,
          flexShrink: 0,
        }}
      >
        Round {round.round_index}
      </div>
      <div style={{ position: 'relative', flex: 1, height: ROW_HEIGHT }}>
        {positioned.map((node, idx) => (
          <div
            key={idx}
            title={`${node.node_name}\n耗时: ${node.duration_ms}ms\n状态: ${node.status}`}
            onClick={() => onNodeClick?.(roundIndex, idx)}
            style={{
              position: 'absolute',
              left: node.left,
              top: (ROW_HEIGHT - BAR_HEIGHT) / 2,
              width: node.width,
              height: BAR_HEIGHT,
              backgroundColor: getNodeColor(node.node_type),
              borderRadius: 4,
              cursor: onNodeClick ? 'pointer' : 'default',
              transition: 'opacity 0.2s',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLDivElement).style.opacity = '0.85';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLDivElement).style.opacity = '1';
            }}
          />
        ))}
      </div>
    </div>
  );
};

const Legend: React.FC = () => (
  <div
    style={{
      display: 'flex',
      gap: 24,
      padding: '12px 0',
      justifyContent: 'center',
      borderTop: `1px solid ${BORDER}`,
    }}
  >
    {Object.entries(NODE_TYPE_COLORS).map(([type, color]) => (
      <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: 2,
            backgroundColor: color,
          }}
        />
        <span style={{ color: TEXT_DIM, fontSize: 12 }}>{getNodeLabel(type)}</span>
      </div>
    ))}
  </div>
);

export const GanttTimeline: React.FC<GanttTimelineProps> = ({ rounds, onNodeClick }) => {
  if (!rounds || rounds.length === 0) {
    return (
      <div
        style={{
          backgroundColor: BG,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
          padding: 24,
          color: TEXT_DIM,
          textAlign: 'center',
        }}
      >
        暂无数据
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: BG,
        border: `1px solid ${BORDER}`,
        borderRadius: 8,
        overflow: 'hidden',
      }}
    >
      <div>
        {rounds.map((round, idx) => (
          <RoundRow
            key={round.round_index}
            round={round}
            roundIndex={idx}
            onNodeClick={onNodeClick}
          />
        ))}
      </div>
      <Legend />
    </div>
  );
};

export default GanttTimeline;
