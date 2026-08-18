import type { TraceRequestSummary } from '../../api/admin';

export function buildTraceMonitorUrl({
  conversationId,
  traceId,
  turnId,
}: {
  conversationId: string;
  traceId?: string | null;
  turnId?: string | null;
}): string {
  const params = new URLSearchParams();
  const cleanTraceId = traceId?.trim();
  const cleanTurnId = turnId?.trim();
  if (cleanTraceId) params.set('trace_id', cleanTraceId);
  if (cleanTurnId) params.set('turn_id', cleanTurnId);
  params.set('conversation_id', conversationId.trim());
  return `/dev/traces?${params.toString()}`;
}

export function selectLatestTraceId(
  traces: Pick<TraceRequestSummary, 'trace_id'>[],
): string | null {
  const first = traces.find((item) => item.trace_id?.trim());
  return first?.trace_id ?? null;
}
