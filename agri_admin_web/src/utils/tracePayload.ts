export type TracePayload = unknown;

const REDACTED = '[REDACTED]';
const SENSITIVE_KEY_RE = /(api[_-]?key|apikey|token|secret|password|authorization)/i;
const SAFE_TOKEN_KEYS = new Set(['token_budget', 'token_estimate', 'token_usage']);
const INLINE_SECRET_RE =
  /\b([a-z0-9_.-]*(?:x-api-key|api[_-]?key|apikey|authorization|token|secret|password|passwd|pwd)[a-z0-9_.-]*)(\s*[:=]\s*)(bearer\s+)?[^\s,;，；。]+/gi;

export function hasTracePayload(value: TracePayload): boolean {
  return value !== null && value !== undefined && value !== '';
}

export function sanitizeTracePayload(value: TracePayload): TracePayload {
  return sanitizeValue(value);
}

export function normalizeTracePayload(value: TracePayload): TracePayload {
  if (!hasTracePayload(value)) return value;
  return normalizeJsonString(value);
}

export function formatTracePayload(value: TracePayload): string {
  if (!hasTracePayload(value)) return '';

  const normalized = normalizeTracePayload(value);

  if (typeof normalized === 'string') {
    return sanitizeText(normalized);
  }

  if (typeof normalized === 'object') {
    return JSON.stringify(sanitizeTracePayload(normalized), null, 2);
  }

  return String(normalized);
}

function normalizeJsonString(value: TracePayload): TracePayload {
  let current = value;

  for (let depth = 0; depth < 3; depth += 1) {
    if (typeof current !== 'string') return current;

    const trimmed = current.trim();
    if (!looksLikeJson(trimmed)) break;

    try {
      current = JSON.parse(trimmed);
    } catch {
      break;
    }
  }

  if (typeof current === 'string') {
    return current.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"');
  }

  return current;
}

function looksLikeJson(value: string): boolean {
  return (
    (value.startsWith('{') && value.endsWith('}')) ||
    (value.startsWith('[') && value.endsWith(']')) ||
    (value.startsWith('"') && value.endsWith('"'))
  );
}

function sanitizeValue(value: TracePayload, keyHint = ''): TracePayload {
  if (keyHint && isSensitiveKey(keyHint)) return REDACTED;

  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item));
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [
        key,
        isSensitiveKey(key) ? REDACTED : sanitizeValue(nested, key),
      ])
    );
  }

  if (typeof value === 'string') {
    return sanitizeText(value);
  }

  return value;
}

function sanitizeText(value: string): string {
  return value.replace(INLINE_SECRET_RE, (_match, key: string, separator: string) => {
    return `${key}${separator}${REDACTED}`;
  });
}

function isSensitiveKey(key: string): boolean {
  const normalized = key.trim().toLowerCase();
  if (SAFE_TOKEN_KEYS.has(normalized)) return false;
  return SENSITIVE_KEY_RE.test(normalized);
}
