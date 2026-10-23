import { MoonOutlined, SunOutlined } from '@ant-design/icons';
import { useThemeMode } from '../theme/themeContext';

export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { mode, setMode } = useThemeMode();

  return (
    <div
      className={`app-theme-toggle${compact ? ' app-theme-toggle--compact' : ''}`}
      role="group"
      aria-label="主题切换"
    >
      <button
        type="button"
        aria-label="亮色主题"
        aria-pressed={mode === 'light'}
        title="亮色主题"
        onClick={() => setMode('light')}
      >
        <SunOutlined />
        {!compact && <span>亮色</span>}
      </button>
      <button
        type="button"
        aria-label="暗色主题"
        aria-pressed={mode === 'dark'}
        title="暗色主题"
        onClick={() => setMode('dark')}
      >
        <MoonOutlined />
        {!compact && <span>暗色</span>}
      </button>
    </div>
  );
}
