import type { ConversationItem } from '../../api/agent';

interface LocalSessionState {
  messages: unknown[];
  loading: boolean;
  traceLoading: boolean;
  timeline?: unknown;
}

export type ConversationRow = ConversationItem & { local?: boolean };

function hasVisibleLocalSession(state: LocalSessionState | undefined): boolean {
  return Boolean(state && (state.messages.length > 0 || state.loading || state.traceLoading));
}

export function buildConversationRows(
  sessions: Record<string, LocalSessionState>,
  conversations: ConversationItem[],
): ConversationRow[] {
  const persistedSessionIds = new Set(conversations.map((conv) => conv.session_id));
  return [
    ...Object.keys(sessions)
      .filter((sid) => !persistedSessionIds.has(sid) && hasVisibleLocalSession(sessions[sid]))
      .map((sid) => ({
        id: -Math.abs(sid.split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0)),
        session_id: sid,
        status: 'active',
        created_at: new Date().toISOString(),
        last_active_at: new Date().toISOString(),
        local: true,
      })),
    ...conversations.map((conv) => ({ ...conv, local: false })),
  ];
}
