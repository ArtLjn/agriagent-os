import { DatabaseOutlined } from '@ant-design/icons';
import './MemoryContextDetails.css';

const STATUS: Record<string, string> = {
  ready: '已完成候选整理', disabled: '已关闭记忆读取', temporary: '临时会话，跳过记忆',
  no_relevant_evidence: '未找到相关依据', unavailable: '记忆处理不可用',
  changed_during_read: '读取期间版本变化，已撤回依据', not_recorded: '旧记录未采集',
};
const RETRIEVAL: Record<string, string> = {
  ready: '语义检索成功', not_configured: 'RAG 未配置，仅使用词项检索',
  lexical_fallback: '语义服务降级为词项检索', timeout: 'RAG 超时，保留词项结果',
  unavailable: 'RAG 不可用，保留词项结果', version_changed: '版本变化，撤回语义候选',
};
const INJECTION: Record<string, string> = {
  included: '已进入本次模型请求', modified: '最终预算修改了记忆块，数量待核查',
  budget_omitted: '最终预算移除了记忆块', not_prepared: '本次未准备记忆块',
  not_in_request: '本次请求未携带准备好的记忆块',
};

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
function count(value: unknown): string {
  return typeof value === 'number' ? String(value) : '未采集';
}

/** 实时事件与历史 Trace 共用展示，缺少最终请求证据时不推断已注入。 */
export function MemoryContextDetails({ data, loading = false, title = '长时记忆' }: {
  data: Record<string, unknown>; loading?: boolean; title?: string;
}) {
  const retrieval = record(data.retrieval);
  const injection = record(data.injection);
  const cards = Array.isArray(retrieval.cards) ? retrieval.cards.map(record) : [];
  const sources = Array.isArray(data.sources) ? data.sources.map(record) : [];
  const sent = new Set(sources.map((source) => source.memory_id));
  const started = data.stage === 'start';
  const final = data.stage === 'complete';
  const included = final && injection.status === 'included';
  const status = started ? (loading ? '正在检索与整理…' : '流程中断，未收到最终结果')
    : STATUS[String(data.status)] ?? String(data.status ?? '旧记录未采集');
  const headline = included && Number(data.injected_count) > 0
    ? `${count(data.injected_count)} 条依据已进入模型请求`
    : final && ['budget_omitted', 'modified', 'not_in_request'].includes(String(injection.status))
      ? INJECTION[String(injection.status)] : status;
  const retrievalStatus = RETRIEVAL[String(retrieval.status)]
    ?? (retrieval.configured === false ? 'RAG 未配置' : '本次未执行检索或未采集');

  return (
    <details className="memory-context">
      <summary className="memory-context__summary">
        <DatabaseOutlined /><strong>{title}</strong>
        <span className={included && Number(data.injected_count) > 0 ? 'memory-context__success' : ''}>{headline}</span>
        {typeof retrieval.status === 'string' && retrieval.status !== 'ready' && <span className="memory-context__warning">{retrievalStatus}</span>}
        <span className="memory-context__toggle">查看流程</span>
      </summary>
      <div className="memory-context__body">
        <div className="memory-context__flow">
          <div><b>01 · 检索</b><span>词项 {count(retrieval.lexical_count)} 张 · RAG {count(retrieval.hit_count)} 张</span></div>
          <div><b>02 · 筛选</b><span>融合保留 {count(retrieval.fused_count)} 张 · 有效依据 {count(data.selected_count)} 条</span></div>
          <div><b>03 · 注入</b><span>{final ? `实际 ${count(data.injected_count)} 条依据` : '等待最终请求核对'}</span></div>
        </div>
        <p>{status} · {retrievalStatus}{data.cached === true ? ' · 复用本轮候选，重新校验版本' : ''}</p>
        <p>{data.mode === 'read' ? '模型阅读筛选' : data.mode === 'retrieve' ? '直接检索筛选' : '筛选模式未采集'}
          {typeof data.elapsed_ms === 'number' && ` · 本次准备 ${data.elapsed_ms} ms`}
          {typeof retrieval.elapsed_ms === 'number' && ` · 检索 ${retrieval.elapsed_ms} ms`}
          {data.code ? ` · ${String(data.code)}` : ''}</p>
        {typeof retrieval.query === 'string' && <div><b>实际检索词</b><pre>{retrieval.query}</pre></div>}
        {typeof retrieval.collection === 'string' && <p>向量集合：{retrieval.collection}
          {Array.isArray(retrieval.actual_modes) && ` · 实际检索方式：${retrieval.actual_modes.join('、')}`}</p>}
        <p>融合排除 {count(retrieval.fusion_dropped_count)} 张 · 版本/有效性排除 {count(data.validation_dropped_count)} 条 · 记忆预算排除 {count(data.budget_dropped_count)} 条</p>
        {cards.length > 0 && <details className="memory-context__evidence">
          <summary>融合后的候选记忆 · {cards.length} 张</summary>
          <div className="memory-context__cards">
          {cards.map((card, index) => <div className="memory-context__card" key={`${String(card.memory_id)}:${index}`}>
            <div className="memory-context__card-meta">
              <span>候选 {index + 1}{typeof card.lexical_rank === 'number' ? ` · 词项 #${card.lexical_rank}` : ''}{typeof card.semantic_rank === 'number' ? ` · RAG #${card.semantic_rank}` : ''}</span>
              <span>{included ? (sent.has(card.memory_id) ? '已注入依据' : '未进入最终依据') : '待最终核对'}</span>
            </div>
            <div>{String(card.text ?? '')}{card.truncated === true ? '…（预览截断）' : ''}</div>
            <small>{String(card.memory_id ?? '')} · 版本 {count(card.revision)}</small>
          </div>)}
          </div>
        </details>}
        <details className="memory-context__evidence">
          <summary>最终请求中的记忆文本</summary>
          <p>{INJECTION[String(injection.status)] ?? '这里只记录了准备结果，不能确认最终发送内容。'}</p>
          {typeof injection.text === 'string' && injection.text && <pre>{injection.text}</pre>}
          {injection.truncated === true && <p>仅展示前 4000 字符，完整请求请查看 LLM Context。</p>}
          {included && data.injected_count === 0 && <p>此块仅包含表达设置与读取状态，没有长期记忆依据。</p>}
        </details>
      </div>
    </details>
  );
}
