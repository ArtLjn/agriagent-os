import { useEffect, useState } from 'react';
import { Typography, Tag, Empty, Spin, Switch, message, Input, Button } from 'antd';
import { AppstoreOutlined, ExperimentOutlined, SearchOutlined } from '@ant-design/icons';
import {
  evaluateSkillRouteRecallDataset,
  listSkills,
  previewSkillRouteRecall,
  updateSkillEnabled,
  type SkillRouteRecallEvalResponse,
  type SkillRouteRecallResponse,
  type SkillItem,
  type SkillSummary,
} from '../../api/admin';

const CARD_BG = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const DISABLE_REASON = '管理员手动禁用';

const EMPTY_SUMMARY: SkillSummary = {
  total: 0,
  enabled: 0,
  disabled: 0,
  admin_only: 0,
};

export default function SkillRegistry() {
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [summary, setSummary] = useState<SkillSummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(false);
  const [updatingSkill, setUpdatingSkill] = useState<string | null>(null);
  const [recallInput, setRecallInput] = useState('');
  const [recallLoading, setRecallLoading] = useState(false);
  const [recallResult, setRecallResult] = useState<SkillRouteRecallResponse | null>(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalResult, setEvalResult] = useState<SkillRouteRecallEvalResponse | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await listSkills();
        setSkills(res.items);
        setSummary(res.summary);
      } catch {
        // 错误已在 api client 中处理
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleToggle = async (skill: SkillItem, enabled: boolean) => {
    setUpdatingSkill(skill.name);
    try {
      const updated = await updateSkillEnabled(skill.name, {
        enabled,
        disabled_reason: enabled ? undefined : DISABLE_REASON,
      });
      setSkills((current) =>
        current.map((item) => (item.name === updated.name ? updated : item))
      );
      setSummary((current) => ({
        ...current,
        enabled: current.enabled + (enabled ? 1 : -1),
        disabled: current.disabled + (enabled ? -1 : 1),
      }));
      message.success(enabled ? 'Skill 已启用' : 'Skill 已禁用');
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setUpdatingSkill(null);
    }
  };

  const handleRecallPreview = async () => {
    const text = recallInput.trim();
    if (!text) {
      message.warning('请输入要测试的业务问题');
      return;
    }
    setRecallLoading(true);
    try {
      const result = await previewSkillRouteRecall({ message: text, top_k: 5 });
      setRecallResult(result);
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setRecallLoading(false);
    }
  };

  const handleDatasetEval = async () => {
    setEvalLoading(true);
    try {
      const result = await evaluateSkillRouteRecallDataset({ top_k: 5 });
      setEvalResult(result);
    } catch {
      // 错误已在 api client 中处理
    } finally {
      setEvalLoading(false);
    }
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        <AppstoreOutlined style={{ marginRight: 8 }} />
        Skill 注册表
      </Typography.Title>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Spin size="large" />
        </div>
      ) : skills.length === 0 ? (
        <Empty description="暂无 Skill 数据" style={{ marginTop: 64 }} />
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
              gap: 12,
              marginBottom: 16,
            }}
          >
            <SummaryCard label="全部 Skill" value={summary.total} />
            <SummaryCard label="已启用" value={summary.enabled} accent="#2ea043" />
            <SummaryCard label="已禁用" value={summary.disabled} accent="#f85149" />
            <SummaryCard label="Admin Only" value={summary.admin_only} accent="#58a6ff" />
          </div>

          <section
            aria-label="Skill 候选召回"
            style={{
              backgroundColor: CARD_BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              padding: 16,
              marginBottom: 16,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: 16,
                alignItems: 'flex-start',
                marginBottom: 12,
              }}
            >
              <div>
                <Typography.Text strong style={{ color: TEXT, fontSize: 16 }}>
                  Skill 候选召回
                </Typography.Text>
              </div>
              <Button
                icon={<ExperimentOutlined aria-hidden />}
                loading={evalLoading}
                onClick={handleDatasetEval}
              >
                运行测试集
              </Button>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 12,
                alignItems: 'end',
                marginBottom: recallResult || evalResult ? 16 : 0,
              }}
            >
              <label htmlFor="skill-recall-input" style={{ display: 'block' }}>
                <span
                  style={{
                    display: 'block',
                    color: TEXT_DIM,
                    fontSize: 13,
                    marginBottom: 6,
                  }}
                >
                  业务输入
                </span>
                <Input
                  id="skill-recall-input"
                  value={recallInput}
                  onChange={(event) => setRecallInput(event.target.value)}
                  onPressEnter={handleRecallPreview}
                  placeholder="例如：这个月花了多少钱"
                />
              </label>
              <Button
                type="primary"
                icon={<SearchOutlined aria-hidden />}
                loading={recallLoading}
                onClick={handleRecallPreview}
                style={{ width: '100%', maxWidth: 180 }}
              >
                测试召回
              </Button>
            </div>

            {recallResult && (
              <>
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    marginBottom: 12,
                  }}
                >
                  <Tag color={recallResult.vector_index_enabled ? 'cyan' : 'orange'}>
                    {recallResult.recall_mode === 'hybrid_vector' ? '混合向量召回' : '本地混合召回'}
                  </Tag>
                  <Tag color={recallResult.vector_index_enabled ? 'green' : 'default'}>
                    {recallResult.vector_index_enabled ? '向量索引已启用' : '向量索引未启用'}
                  </Tag>
                  <Tag color={recallBool(recallResult.recall, 'quillrag_retrieve_used') ? 'green' : 'default'}>
                    {recallBool(recallResult.recall, 'quillrag_retrieve_used') ? 'RAG 已调用' : 'RAG 未调用'}
                  </Tag>
                  <Tag color={recallBool(recallResult.recall, 'external_embedding_requested') ? 'cyan' : 'default'}>
                    Embedding: {recallText(recallResult.recall, 'embedding_location') || 'none'}
                  </Tag>
                  <Tag color="blue">
                    Scope: {recallText(recallResult.recall, 'candidate_scope') || 'unknown'}
                  </Tag>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                    gap: 12,
                    marginBottom: evalResult ? 16 : 0,
                  }}
                >
                  {recallResult.candidates.length === 0 ? (
                    <div style={{ color: TEXT_DIM }}>未召回候选 Skill</div>
                  ) : (
                    recallResult.candidates.map((candidate, index) => (
                      <div
                        key={`${candidate.skill}-${candidate.operation ?? 'none'}`}
                        style={{
                          backgroundColor: '#0d1117',
                          border: `1px solid ${BORDER}`,
                          borderRadius: 6,
                          padding: 12,
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: 8,
                            marginBottom: 8,
                          }}
                        >
                          <Typography.Text strong style={{ color: TEXT }}>
                            #{index + 1} {candidate.skill}
                          </Typography.Text>
                          <Typography.Text style={{ color: '#58a6ff' }}>
                            hybrid {candidate.score.toFixed(3)}
                          </Typography.Text>
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                          {candidate.operation && (
                            <Tag color="blue">{candidate.operation}</Tag>
                          )}
                          <Tag color={riskColor(candidate.operation_risk || candidate.risk)}>
                            {candidate.operation_risk || candidate.risk}
                          </Tag>
                          {evidenceSources(candidate.evidence).map((source) => (
                            <Tag key={source} color={sourceColor(source)}>
                              {source}
                            </Tag>
                          ))}
                        </div>
                        <EvidenceMetrics evidence={candidate.evidence} />
                      </div>
                    ))
                  )}
                </div>
              </>
            )}

            {recallResult?.skill_router && (
              <details
                open
                style={{
                  backgroundColor: '#0d1117',
                  border: `1px solid ${BORDER}`,
                  borderRadius: 6,
                  padding: 12,
                  marginBottom: evalResult ? 16 : 0,
                }}
              >
                <summary
                  style={{
                    color: TEXT,
                    cursor: 'pointer',
                    fontWeight: 600,
                    marginBottom: 10,
                  }}
                >
                  skill_router trace JSON
                </summary>
                <pre
                  aria-label="skill_router trace JSON"
                  style={{
                    color: TEXT,
                    fontSize: 12,
                    lineHeight: 1.5,
                    margin: 0,
                    maxHeight: 420,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(recallResult.skill_router, null, 2)}
                </pre>
              </details>
            )}

            {evalResult && (
              <>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: 12,
                  }}
                >
                  <Metric label="测试集" value={evalResult.dataset.path} />
                  <Metric label="样本数" value={String(evalResult.report.total)} />
                  <Metric label="Recall@1" value={formatPercent(evalResult.report.recall_at_1)} />
                  <Metric label={`Recall@${evalResult.top_k}`} value={formatPercent(evalResult.report.recall_at_k)} />
                  <Metric
                    label={`Operation@${evalResult.top_k}`}
                    value={formatPercent(evalResult.report.operation_recall_at_k)}
                  />
                  <Metric label="失败样本" value={String(evalResult.report.failures.length)} />
                </div>
                {evalResult.report.failures.length > 0 && (
                  <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
                    {evalResult.report.failures.map((failure) => (
                      <div
                        key={failure.case_id}
                        style={{
                          backgroundColor: '#0d1117',
                          border: `1px solid ${BORDER}`,
                          borderRadius: 6,
                          padding: 12,
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            flexWrap: 'wrap',
                            gap: 8,
                            marginBottom: 8,
                          }}
                        >
                          <Typography.Text strong style={{ color: TEXT }}>
                            {failure.case_id}
                          </Typography.Text>
                          <Tag color="error">
                            {routeLabel(failure.expected)}
                          </Tag>
                        </div>
                        <div
                          style={{
                            color: TEXT,
                            fontSize: 14,
                            marginBottom: 8,
                            overflowWrap: 'anywhere',
                          }}
                        >
                          {failure.message}
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                          {failure.top_k.map((route) => (
                            <Tag key={routeLabel(route)} color="default">
                              {routeLabel(route)}
                            </Tag>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </section>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
              gap: 16,
            }}
          >
            {skills.map((skill) => (
              <div
                key={skill.name}
                style={{
                  backgroundColor: CARD_BG,
                  border: `1px solid ${BORDER}`,
                  borderRadius: 8,
                  padding: 20,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    alignItems: 'center',
                    marginBottom: 12,
                  }}
                >
                  <Typography.Text
                    strong
                    style={{ color: TEXT, fontSize: 16 }}
                  >
                    {skill.name}
                  </Typography.Text>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <Tag color={statusColor(skill.status)}>
                      {skill.status}
                    </Tag>
                    <Switch
                      aria-label={`${skill.metadata.enabled ? '禁用' : '启用'} ${skill.name}`}
                      checked={skill.metadata.enabled}
                      loading={updatingSkill === skill.name}
                      size="small"
                      onChange={(checked) => handleToggle(skill, checked)}
                    />
                  </div>
                </div>

                <div
                  style={{
                    color: TEXT_DIM,
                    marginBottom: 12,
                    fontSize: 14,
                    lineHeight: 1.6,
                  }}
                >
                  {skill.description}
                </div>

                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 8,
                    marginBottom: 12,
                  }}
                >
                  <Tag color="blue">{skill.metadata.permission_level}</Tag>
                  <Tag color={riskColor(skill.metadata.risk_level)}>
                    {skill.metadata.risk_level}
                  </Tag>
                </div>

                {skill.metadata.disabled_reason && (
                  <div
                    style={{
                      color: '#f85149',
                      marginBottom: 12,
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}
                  >
                    {skill.metadata.disabled_reason}
                  </div>
                )}

                <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 4 }}>
                  参数 schema:
                </div>
                <pre
                  style={{
                    backgroundColor: '#0d1117',
                    border: `1px solid ${BORDER}`,
                    borderRadius: 4,
                    padding: 12,
                    color: TEXT,
                    fontSize: 12,
                    overflow: 'auto',
                    maxHeight: 240,
                    margin: 0,
                  }}
                >
                  {JSON.stringify(skill.parameters_schema, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        backgroundColor: '#0d1117',
        border: `1px solid ${BORDER}`,
        borderRadius: 6,
        padding: 12,
        minWidth: 0,
      }}
    >
      <div style={{ color: TEXT_DIM, fontSize: 12, marginBottom: 6 }}>
        {label}
      </div>
      <div
        style={{
          color: TEXT,
          fontSize: 18,
          fontWeight: 700,
          overflowWrap: 'anywhere',
        }}
      >
        {value}
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  accent = '#8b949e',
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div
      style={{
        backgroundColor: CARD_BG,
        border: `1px solid ${BORDER}`,
        borderTop: `2px solid ${accent}`,
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ color: TEXT_DIM, fontSize: 13, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ color: TEXT, fontSize: 26, fontWeight: 700 }}>
        {value}
      </div>
    </div>
  );
}

function EvidenceMetrics({ evidence }: { evidence: Record<string, unknown> }) {
  const metrics = ['bm25', 'vector', 'lexical']
    .map((key) => evidenceMetric(evidence, key))
    .filter((item): item is string => Boolean(item));

  if (metrics.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 8,
        marginTop: 10,
      }}
    >
      {metrics.map((metric) => (
        <Typography.Text key={metric} style={{ color: TEXT_DIM, fontSize: 12 }}>
          {metric}
        </Typography.Text>
      ))}
    </div>
  );
}

function statusColor(status: string) {
  if (status === 'active') {
    return 'success';
  }
  if (status === 'disabled') {
    return 'error';
  }
  if (status === 'admin_only') {
    return 'processing';
  }
  return 'default';
}

function riskColor(risk: string) {
  if (risk === 'high' || risk === 'write_high') {
    return 'red';
  }
  if (risk === 'medium' || risk === 'write_confirm') {
    return 'orange';
  }
  return 'green';
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function routeLabel(route: { skill: string; operation: string | null }) {
  return route.operation ? `${route.skill}.${route.operation}` : route.skill;
}

function evidenceSources(evidence: Record<string, unknown>) {
  const sources = evidence.sources;
  if (!Array.isArray(sources)) {
    return [];
  }
  return sources.filter((source): source is string => typeof source === 'string');
}

function evidenceMetric(evidence: Record<string, unknown>, key: string) {
  const value = evidence[key];
  if (typeof value !== 'number') {
    return null;
  }
  return `${key}: ${value.toFixed(2)}`;
}

function recallBool(recall: Record<string, unknown> | undefined, key: string) {
  return Boolean(recall?.[key]);
}

function recallText(recall: Record<string, unknown> | undefined, key: string) {
  const value = recall?.[key];
  return typeof value === 'string' ? value : '';
}

function sourceColor(source: string) {
  if (source === 'lexical') {
    return 'purple';
  }
  if (source === 'vector') {
    return 'cyan';
  }
  if (source === 'bm25') {
    return 'geekblue';
  }
  return 'default';
}
