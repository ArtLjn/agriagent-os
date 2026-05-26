export interface GanttNode {
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  start_time: string | null;
}

export interface GanttRound {
  round_index: number;
  nodes: GanttNode[];
}

export interface GanttTimelineProps {
  rounds: GanttRound[];
  onNodeClick?: (roundIndex: number, nodeIndex: number) => void;
}
