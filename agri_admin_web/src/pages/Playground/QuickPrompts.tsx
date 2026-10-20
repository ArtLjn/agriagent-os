import type { ReactNode } from 'react';
import {
  CalendarOutlined,
  FileAddOutlined,
  PayCircleOutlined,
  SearchOutlined,
  SunOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { palette } from '../../styles/theme';
import { QUICK_PROMPTS } from './quickPromptList';

/* 快捷提示词图标按 key 映射，统一用 antd 图标 + palette 色，不再用 emoji */
const PROMPT_ICONS: Record<string, { icon: ReactNode; color: string }> = {
  cost: { icon: <PayCircleOutlined />, color: palette.warning },
  worker: { icon: <TeamOutlined />, color: palette.accent },
  'crop-cycle': { icon: <CalendarOutlined />, color: palette.success },
  'work-order': { icon: <FileAddOutlined />, color: palette.purple },
  weather: { icon: <SunOutlined />, color: palette.warning },
  search: { icon: <SearchOutlined />, color: palette.accent },
};

export function QuickPrompts({
  onSelect,
  disabled,
}: {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
}) {
  return (
    <div role="list" className="pg-prompts">
      {QUICK_PROMPTS.map((p) => {
        const meta = PROMPT_ICONS[p.key] ?? { icon: <SearchOutlined />, color: palette.accent };
        return (
          <button
            key={p.key}
            type="button"
            role="listitem"
            className="pg-prompt"
            disabled={disabled}
            onClick={() => onSelect(p.prompt)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span
                className="pg-prompt__icon"
                style={{ color: meta.color, background: `${meta.color}1f` }}
              >
                {meta.icon}
              </span>
              <span className="pg-prompt__title">{p.title}</span>
            </div>
            <div className="pg-prompt__desc">{p.description}</div>
          </button>
        );
      })}
    </div>
  );
}
