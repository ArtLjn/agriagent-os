export type TracePayload = unknown;

export function hasTracePayload(value: TracePayload): boolean {
  return value !== null && value !== undefined && value !== '';
}

export function formatTracePayload(value: TracePayload): string {
  if (!hasTracePayload(value)) return '';

  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"');
    }
  }

  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }

  return String(value);
}
