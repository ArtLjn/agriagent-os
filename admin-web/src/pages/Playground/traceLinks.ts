import type { TraceRequestSummary } from '../../api/admin';

export function buildTraceMonitorUrl({
  conversationId,
  requestId,
}: {
  conversationId: string;
  requestId?: string | null;
}): string {
  const params = new URLSearchParams();
  const cleanRequestId = requestId?.trim();
  if (cleanRequestId) params.set('request_id', cleanRequestId);
  params.set('conversation_id', conversationId);
  return `/dev/traces?${params.toString()}`;
}

export function selectLatestTraceRequestId(
  traces: Pick<TraceRequestSummary, 'request_id'>[],
): string | null {
  const first = traces.find((item) => item.request_id.trim());
  return first?.request_id ?? null;
}
