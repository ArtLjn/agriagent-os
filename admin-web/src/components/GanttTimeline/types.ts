import type { TracePayload } from '../../utils/tracePayload';

export interface GanttNode {
  id?: number | string | null;
  node_type: string;
  node_name: string;
  duration_ms: number | null;
  status: string;
  start_time: string | null;
  end_time?: string | null;
  input_data?: TracePayload;
  output_data?: TracePayload;
  token_usage?: Record<string, unknown> | null;
  error_message?: string | null;
  error_code?: string | null;
  recover?: string | null;
  trace_id?: string;
  span_id?: string | null;
  parent_span_id?: string | null;
  span_kind?: string;
  layer?: string;
  phase?: string | null;
  attempt?: number | null;
  attributes?: Record<string, unknown>;
  resource?: Record<string, unknown>;
  sampling?: Record<string, unknown>;
}

export interface GanttRound {
  round_index: number;
  nodes: GanttNode[];
}

export interface GanttTimelineProps {
  rounds: GanttRound[];
  onNodeClick?: (roundIndex: number, nodeIndex: number, node: GanttNode) => void;
}
