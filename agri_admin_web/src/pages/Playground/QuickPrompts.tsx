import { palette } from '../../styles/theme';
import { QUICK_PROMPTS } from './quickPromptList';

const CARD = palette.bgElevated;
const BORDER = palette.border;
const TEXT = palette.text;
const TEXT_DIM = palette.textMuted;
const ACCENT = palette.accent;
const CARD_HOVER_BG = 'rgba(88, 166, 255, 0.06)';

export function QuickPrompts({
  onSelect,
  disabled,
}: {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="list"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 10,
        maxWidth: 720,
        width: '100%',
        marginTop: 24,
      }}
    >
      {QUICK_PROMPTS.map((p) => (
        <button
          key={p.key}
          type="button"
          role="listitem"
          disabled={disabled}
          onClick={() => onSelect(p.prompt)}
          style={{
            textAlign: 'left',
            background: CARD,
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            padding: '12px 14px',
            cursor: disabled ? 'not-allowed' : 'pointer',
            color: TEXT,
            transition: 'border-color 120ms ease, background 120ms ease',
            opacity: disabled ? 0.5 : 1,
          }}
          onMouseEnter={(e) => {
            if (disabled) return;
            e.currentTarget.style.borderColor = ACCENT;
            e.currentTarget.style.background = CARD_HOVER_BG;
          }}
          onMouseLeave={(e) => {
            if (disabled) return;
            e.currentTarget.style.borderColor = BORDER;
            e.currentTarget.style.background = CARD;
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 16, lineHeight: 1 }}>{p.icon}</span>
            <span style={{ fontSize: 13, fontWeight: 500, color: TEXT }}>{p.title}</span>
          </div>
          <div style={{ fontSize: 12, color: TEXT_DIM, lineHeight: 1.5 }}>
            {p.description}
          </div>
        </button>
      ))}
    </div>
  );
}
