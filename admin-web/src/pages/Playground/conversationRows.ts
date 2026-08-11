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
  const persistedIds = new Set(conversations.map((conv) => conv.conversation_id));
  return [
    ...Object.keys(sessions)
      .filter((sid) => !persistedIds.has(sid) && hasVisibleLocalSession(sessions[sid]))
      .map((sid) => ({
        conversation_id: sid,
        last_message: '',
        last_role: '',
        last_at: new Date().toISOString(),
        message_count: 0,
        local: true,
      })),
    ...conversations.map((conv) => ({ ...conv, local: false })),
  ];
}
