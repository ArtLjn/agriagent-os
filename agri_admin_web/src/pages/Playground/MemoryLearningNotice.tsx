import { useEffect, useState } from 'react';
import { CheckOutlined, LoadingOutlined } from '@ant-design/icons';
import { getMemoryLearningStatus, type MemoryLearningStatus } from '../../api/agent';

// 学习在聊天流结束后继续；只轮询当前最后一轮，有界退出，历史记录读取一次。
const POLL_INTERVAL_MS = 5000;
const MAX_POLLS = 60;
const ACTIVE_STATUSES = new Set(['not_observed', 'pending', 'queued', 'running']);

export function MemoryLearningNotice({ turnId, userToken, watch }: {
  turnId: string; userToken?: string | null; watch: boolean;
}) {
  const [result, setResult] = useState<MemoryLearningStatus | null>(null);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    async function refresh() {
      attempts += 1;
      try {
        const next = await getMemoryLearningStatus(turnId, userToken);
        if (cancelled) return;
        setResult(next);
        const keepWatching = watch && attempts < MAX_POLLS && ACTIVE_STATUSES.has(next.status);
        setWaiting(keepWatching);
        if (keepWatching) timer = setTimeout(refresh, POLL_INTERVAL_MS);
      } catch {
        if (!cancelled) {
          setResult({ status: 'unavailable' });
          setWaiting(false);
        }
      }
    }
    void refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [turnId, userToken, watch]);

  if (!result || ['not_observed', 'temporary', 'disabled', 'sensitive', 'control_changed', 'input_too_long'].includes(result.status)) return null;
  const saved = result.status === 'done' && Number(result.applied_count) > 0;
  let label = '后台学习状态暂时不可用';
  if (ACTIVE_STATUSES.has(result.status)) label = waiting
    ? '听到啦，正在整理你说的话…' : '听到啦，已交给后台整理，可稍后查看记忆';
  if (result.status === 'done') label = saved
    ? `已记住，这次整理了 ${result.applied_count} 条记忆`
    : result.reason === 'control_changed' ? '记忆设置已变化，本次没有保存' : '听到啦，这次没有需要长期记住的新内容';
  if (result.status === 'failed') label = '听到啦，但这次记忆整理未成功';
  return <div className={`memory-learning-notice${saved ? ' memory-learning-notice--saved' : ''}`} role="status" aria-live="polite">
    {waiting ? <LoadingOutlined spin /> : saved ? <CheckOutlined /> : null}<span>{label}</span>
  </div>;
}
