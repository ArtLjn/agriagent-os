import { useMemo, useState } from 'react';
import { Button, Tag } from 'antd';
import { MessageOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PageShell } from '../../components/PageShell';
import './companion.css';

type Mood = 'happy' | 'okay' | 'tired' | 'low' | 'anxious';

interface MoodEntry {
  date: string;
  mood: Mood;
}

const STORAGE_KEY = 'tianzhanggui-companion-moods';

const MOODS: { key: Mood; label: string; hint: string }[] = [
  { key: 'happy', label: '很好', hint: '今天有光' },
  { key: 'okay', label: '还行', hint: '平稳就好' },
  { key: 'tired', label: '有点累', hint: '需要歇一会儿' },
  { key: 'low', label: '低落', hint: '不用马上好起来' },
  { key: 'anxious', label: '焦虑', hint: '先把节奏放慢' },
];

const SUGGESTIONS: Record<Mood, string> = {
  happy: '把今天让你开心的一件小事记下来，留到以后再看。',
  okay: '起身喝一杯水，顺手伸展一下肩颈。',
  tired: '放下手里的事，闭眼休息五分钟，让肩膀自然下沉。',
  low: '给一个信任的人发一条很短的消息，不需要解释太多。',
  anxious: '慢慢呼吸：吸气四秒，停两秒，呼气六秒，重复几轮。',
};

function todayKey(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function readMoods(): MoodEntry[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item): item is MoodEntry => (
        typeof item?.date === 'string'
        && MOODS.some((mood) => mood.key === item?.mood)
      ),
    );
  } catch {
    return [];
  }
}

function storeMoods(entries: MoodEntry[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, 30)));
  } catch {
    // 隐私模式下存储不可用时仅本次会话生效
  }
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了，先把节奏放慢一点。';
  if (hour < 12) return '早上好。今天不用一下子进入状态。';
  if (hour < 18) return '下午好。今天已经走了这么远，可以稍微停一下。';
  return '晚上好。今天不管过得怎样，现在可以先把自己放下来。';
}

function moodLabel(mood: Mood): string {
  return MOODS.find((item) => item.key === mood)?.label ?? mood;
}

export default function CompanionSpace() {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<MoodEntry[]>(readMoods);
  const today = todayKey();
  const current = entries.find((entry) => entry.date === today);
  const recent = useMemo(() => entries.slice(0, 7), [entries]);

  const selectMood = (mood: Mood) => {
    const next = [
      { date: today, mood },
      ...entries.filter((entry) => entry.date !== today),
    ];
    setEntries(next);
    storeMoods(next);
  };

  return (
    <PageShell
      title="陪伴空间"
      description="给今天留一点被照顾的时间。这里不评判、不催促，只陪你待一会儿。"
      actions={(
        <Button type="primary" icon={<MessageOutlined />} onClick={() => navigate('/companion/chat')}>
          和陪伴助手聊聊
        </Button>
      )}
    >
      <section className="companion-hero">
        <div>
          <span className="companion-hero__eyebrow">
            {new Date().toLocaleDateString('zh-CN', {
              month: 'long',
              day: 'numeric',
              weekday: 'long',
            })}
          </span>
          <h2>{greeting()}</h2>
          <p>你可以先说说此刻的状态，也可以什么都不做，只是在这里坐一会儿。</p>
        </div>
        <div className="companion-hero__note">
          <span>今天的照顾</span>
          <strong>慢一点也算前进</strong>
        </div>
      </section>

      <section className="companion-section" aria-label="心情记录">
        <div className="companion-section__head">
          <h3>此刻的你</h3>
          <span>选一个最接近的状态，不需要准确。</span>
        </div>
        <div className="companion-moods">
          {MOODS.map((mood) => (
            <button
              key={mood.key}
              type="button"
              className="companion-mood"
              data-mood={mood.key}
              data-selected={current?.mood === mood.key}
              aria-pressed={current?.mood === mood.key}
              onClick={() => selectMood(mood.key)}
            >
              <strong>{mood.label}</strong>
              <span>{mood.hint}</span>
            </button>
          ))}
        </div>
      </section>

      <div className="companion-grid">
        <section className="companion-card">
          <span className="companion-card__eyebrow">给此刻的你</span>
          <h3>{current ? `看到你了：${moodLabel(current.mood)}` : '先照顾好此刻'}</h3>
          <p>{current ? SUGGESTIONS[current.mood] : '选一个状态，我会给你一个五分钟内能完成的小动作。'}</p>
          {current && <Tag bordered={false}>今天已记录</Tag>}
        </section>

        <section className="companion-card">
          <span className="companion-card__eyebrow">随时可以做</span>
          <h3>三件很小的照顾</h3>
          <ul className="companion-care-list">
            <li>喝一杯水，哪怕只喝两口。</li>
            <li>离开屏幕站一会儿，看看远处。</li>
            <li>给一个信任的人发条消息，不必解释很多。</li>
          </ul>
        </section>
      </div>

      <section className="companion-section" aria-label="最近的心情">
        <div className="companion-section__head">
          <h3>最近七天</h3>
          <span>只保存在这台设备上。</span>
        </div>
        {recent.length === 0 ? (
          <p className="companion-empty">还没有记录。今天可以从一个词开始。</p>
        ) : (
          <div className="companion-recent">
            {recent.map((entry) => (
              <span key={entry.date} className="companion-recent__item">
                <em>{entry.date.slice(5)}</em>
                <strong>{moodLabel(entry.mood)}</strong>
              </span>
            ))}
          </div>
        )}
      </section>

      <p className="companion-boundary">
        陪伴助手不是心理医生，也不能替代专业帮助。如果你正处在紧急危险中，
        请立即联系身边信任的人、拨打 120 或 110。
      </p>
    </PageShell>
  );
}
