import type { TraceRecord } from '../../api/admin';

export function buildTraceMonitorUrl({
  sessionId,
  requestId,
}: {
  sessionId: string;
  requestId?: string | null;
}): string {
  const params = new URLSearchParams();
  const cleanRequestId = requestId?.trim();
  if (cleanRequestId) params.set('request_id', cleanRequestId);
  params.set('session_id', sessionId);
  return `/dev/traces?${params.toString()}`;
}

export function selectLatestTraceRequestId(
  traces: Pick<TraceRecord, 'request_id'>[],
): string | null {
  const first = traces.find((item) => item.request_id.trim());
  return first?.request_id ?? null;
}
