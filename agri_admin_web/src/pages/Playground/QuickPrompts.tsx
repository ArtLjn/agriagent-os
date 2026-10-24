import { useEffect, useState } from 'react';
import { ArrowRightOutlined, BulbOutlined, CompassOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  getQuestionRecommendations,
  RECOMMENDATION_HISTORY_LIMIT,
  type QuestionRecommendations,
} from '../../api/questionRecommendations';

interface RecommendationState {
  owner: string | null;
  version: number;
  data?: QuestionRecommendations;
  failed?: boolean;
}

export function QuickPrompts({ onSelect, disabled, userToken = null }: {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
  userToken?: string | null;
}) {
  const [request, setRequest] = useState({ owner: userToken, version: 0, exclude: [] as string[] });
  const [result, setResult] = useState<RecommendationState | null>(null);
  // 身份改变的首次渲染立即隐藏旧内容，不能等异步请求完成才清空。
  const current = result?.owner === userToken && result.version === request.version ? result : null;
  const loading = current === null;

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void getQuestionRecommendations(
      request.owner === userToken ? request.exclude : [], userToken, controller.signal,
    ).then((data) => {
      if (active) setResult({ owner: userToken, version: request.version, data });
    }).catch(() => {
      if (active) setResult({ owner: userToken, version: request.version, failed: true });
    });
    return () => { active = false; controller.abort(); };
  }, [userToken, request]);

  const refresh = () => {
    const previous = request.owner === userToken ? request.exclude : [];
    const questions = current?.data?.items.map((item) => item.question) ?? [];
    setRequest({
      owner: userToken,
      version: request.version + 1,
      exclude: [...new Set([...previous, ...questions])].slice(-RECOMMENDATION_HISTORY_LIMIT),
    });
  };

  return (
    <section className="pg-recommendations" aria-label="推荐问题" aria-busy={loading}>
      <div className="pg-recommendations__header">
        <div>
          <h2>猜你想问<span className="pg-recommendations__spark" aria-hidden>✦</span></h2>
          <p>{current?.data?.mode === 'personalized' ? '结合你已保存的兴趣与偏好' : '发现值得聊一聊的话题'}</p>
        </div>
        <button type="button" className="pg-recommendations__refresh" onClick={refresh} disabled={disabled || loading}>
          <ReloadOutlined spin={loading} aria-hidden /> {loading ? '生成中' : '换一批'}
        </button>
      </div>
      {loading ? (
        <div className="pg-recommendations__loading" role="status">
          <span className="pg-recommendations__sr-only">正在为你准备问题…</span>
          <div className="pg-prompts" aria-hidden>
            {Array.from({ length: 6 }, (_, index) => (
              <div className="pg-prompt pg-prompt--skeleton" key={index}>
                <span className="pg-prompt__icon" />
                <span className="pg-prompt__skeleton-lines"><i /><i /></span>
              </div>
            ))}
          </div>
        </div>
      ) : current?.failed ? (
        <div className="pg-recommendations__status" role="status">
          <span>推荐暂时不可用，你仍可直接输入问题。</span>
          <button type="button" onClick={refresh} disabled={disabled}>重试</button>
        </div>
      ) : current?.data?.items.length ? (
        <ul className="pg-prompts">
          {current.data.items.map((item) => (
            <li key={item.id}>
              <button type="button" className={`pg-prompt pg-prompt--${item.basis}`} disabled={disabled}
                aria-label={item.question} title={item.question} onClick={() => onSelect(item.question)}>
                <span className="pg-prompt__icon" title={item.basis === 'memory' ? '结合你的偏好' : '探索话题'} aria-hidden>
                  {item.basis === 'memory' ? <BulbOutlined /> : <CompassOutlined />}
                </span>
                <span className="pg-prompt__title">{item.question}</span>
                <ArrowRightOutlined className="pg-prompt__arrow" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="pg-recommendations__status" role="status">暂时没有新问题，可以换一批或直接输入。</div>
      )}
      <p className="pg-recommendations__note">选一个你想问 AI 的问题，编辑后发送</p>
    </section>
  );
}
