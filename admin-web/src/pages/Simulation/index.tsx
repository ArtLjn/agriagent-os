import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card, Button, Input, Select, Table, Tag, Progress, Space,
  Row, Col, Checkbox, Collapse, Alert, Typography, Badge, Spin, message,
} from 'antd';
import {
  ExperimentOutlined, PlayCircleOutlined, ReloadOutlined,
  CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import apiClient from '../../api/client';

const { Text, Title } = Typography;
const { Panel } = Collapse;
const { Option } = Select;

// ─── Types ───────────────────────────────────────────────────────────

interface SimulationCase {
  case_id: string;
  description: string;
  user_input: string;
  category: string;
  expected_response_matches: string[];
  expected_db_changes: Record<string, unknown>;
  verify_tables: string[];
}

interface DbDiff {
  added: Array<Record<string, unknown>>;
  removed: Array<Record<string, unknown>>;
  modified: Array<Record<string, unknown>>;
}

interface ExtractedClaim {
  op_type: string;
  description: string;
  keywords_matched: string[];
}

interface SimulationResult {
  case_id: string;
  passed: boolean;
  agent_reply: string;
  errors: string[];
  db_diff: DbDiff;
  extracted_claims: ExtractedClaim[];
  latency_ms: number;
  category: string;
  user_input: string;
  pending_action: Record<string, unknown> | null;
  expected_db_changes: Record<string, unknown>;
}

interface RunStatus {
  run_id: string;
  status: string;
  total: number;
  passed?: number;
  failed?: number;
  progress: { current: number; total: number };
  results: SimulationResult[];
  error?: string;
}

interface RunSummary {
  run_id: string;
  status: string;
  passed: number;
  failed: number;
  created_at: string;
}

// ─── Constants ───────────────────────────────────────────────────────

const CATEGORIES = ['basic', 'error', 'hallucination', 'partial', 'pending'];

const CATEGORY_COLORS: Record<string, string> = {
  basic: 'blue',
  error: 'orange',
  hallucination: 'red',
  partial: 'purple',
  pending: 'default',
};

// ─── Helper Components ───────────────────────────────────────────────

function ClaimComparisonTable({ claims, dbDiff }: { claims: ExtractedClaim[]; dbDiff: DbDiff }) {
  const hasDiff = dbDiff.added.length > 0 || dbDiff.removed.length > 0 || dbDiff.modified.length > 0;

  return (
    <div style={{ marginTop: 16 }}>
      <Title level={5}>声称 vs 现实 对比</Title>
      <Table
        size="small"
        pagination={false}
        dataSource={claims.map((c, i) => ({ ...c, key: i }))}
        columns={[
          {
            title: 'LLM 声称',
            dataIndex: 'description',
            render: (text: string, record: ExtractedClaim) => (
              <Space direction="vertical" size={0}>
                <Tag color="blue">{record.op_type}</Tag>
                <Text>{text}</Text>
              </Space>
            ),
          },
          {
            title: '数据库实际',
            render: (_: unknown, record: ExtractedClaim) => {
              const matched = record.keywords_matched.length > 0;
              return (
                <Space direction="vertical" size={0}>
                  {matched ? (
                    <Tag color="success">已验证</Tag>
                  ) : (
                    <Tag color="error">未找到匹配</Tag>
                  )}
                  <Text type="secondary">
                    关键词匹配: {record.keywords_matched.join(', ') || '无'}
                  </Text>
                </Space>
              );
            },
          },
          {
            title: '判定',
            render: (_: unknown, record: ExtractedClaim) => {
              const matched = record.keywords_matched.length > 0;
              return matched ? (
                <Tag icon={<CheckCircleOutlined />} color="success">匹配</Tag>
              ) : (
                <Tag icon={<CloseCircleOutlined />} color="error">不匹配</Tag>
              );
            },
          },
        ]}
      />
      {hasDiff && (
        <Collapse ghost style={{ marginTop: 8 }}>
          <Panel header="数据库差异 (db_diff)" key="1">
            {dbDiff.added.length > 0 && (
              <Alert message="新增记录" description={<pre>{JSON.stringify(dbDiff.added, null, 2)}</pre>} type="info" showIcon />
            )}
            {dbDiff.removed.length > 0 && (
              <Alert message="删除记录" description={<pre>{JSON.stringify(dbDiff.removed, null, 2)}</pre>} type="warning" showIcon />
            )}
            {dbDiff.modified.length > 0 && (
              <Alert message="修改记录" description={<pre>{JSON.stringify(dbDiff.modified, null, 2)}</pre>} type="error" showIcon />
            )}
          </Panel>
        </Collapse>
      )}
    </div>
  );
}

function MetaTags({ result }: { result: SimulationResult }) {
  const added = result.db_diff.added.length;
  const removed = result.db_diff.removed.length;
  const modified = result.db_diff.modified.length;
  const hasPending = !!result.pending_action;

  return (
    <Space wrap style={{ marginTop: 8 }}>
      <Tag icon={<ClockCircleOutlined />} color="default">{result.latency_ms}ms</Tag>
      <Tag color={CATEGORY_COLORS[result.category] || 'default'}>{result.category}</Tag>
      {hasPending && (
        <Tag color="purple">
          pending: {(result.pending_action as Record<string, string>)?.skill_name}
        </Tag>
      )}
      <Tag color={added > 0 ? 'success' : 'default'}>新增 {added}</Tag>
      <Tag color={modified > 0 ? 'warning' : 'default'}>修改 {modified}</Tag>
      <Tag color={removed > 0 ? 'error' : 'default'}>删除 {removed}</Tag>
    </Space>
  );
}

function ExpectedVsActual({ expected, actual }: { expected: Record<string, unknown>; actual: DbDiff }) {
  if (!expected || Object.keys(expected).length === 0) {
    return (
      <Alert
        style={{ marginTop: 12 }}
        message="预期变化"
        description="无预期变化（预期 DB 应保持不变）"
        type="info"
        showIcon
      />
    );
  }

  return (
    <div style={{ marginTop: 12 }}>
      <Title level={5}>预期变化 vs 实际变化</Title>
      {Object.entries(expected).map(([table, expect]) => {
        const exp = expect as Record<string, unknown>;
        const expectedAdded = (exp?.added as number) || 0;
        const actualAdded = actual.added.filter(r => r.__table__ === table).length;
        const match = expectedAdded === actualAdded;

        return (
          <Card
            key={table}
            size="small"
            style={{ marginBottom: 8 }}
            title={
              <Space>
                <Text strong>{table}</Text>
                <Tag color={match ? 'success' : 'error'}>
                  预期新增 {expectedAdded} / 实际新增 {actualAdded}
                </Tag>
              </Space>
            }
          >
            {exp?.match_fields && (
              <Text type="secondary">
                匹配字段: {JSON.stringify(exp.match_fields)}
              </Text>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function getErrorTag(err: string): { color: string; label: string } {
  const type = err.split(':')[0];
  const map: Record<string, { color: string; label: string }> = {
    hallucination: { color: 'red', label: '幻觉' },
    execution_failure: { color: 'orange', label: '执行失败' },
    state_mismatch: { color: 'gold', label: '状态不匹配' },
    response_mismatch: { color: 'blue', label: '响应不匹配' },
    attribution_error: { color: 'purple', label: '错误归因' },
    silent_mutation: { color: 'magenta', label: '静默变更' },
    runner_exception: { color: 'default', label: '引擎异常' },
  };
  return map[type] || { color: 'default', label: '其他' };
}

function ResultDetail({ result }: { result: SimulationResult }) {
  return (
    <div style={{ padding: '16px 0' }}>
      {/* 元信息 */}
      <MetaTags result={result} />

      {/* 输入 / 回复 */}
      <Row gutter={[24, 16]} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card size="small" title="用户输入" style={{ height: '100%' }}>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{result.user_input}</Text>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="LLM 回复" style={{ height: '100%' }}>
            <Text style={{ whiteSpace: 'pre-wrap' }}>{result.agent_reply}</Text>
          </Card>
        </Col>
      </Row>

      {/* Pending Action */}
      {result.pending_action && (
        <Alert
          style={{ marginTop: 16 }}
          message="Pending Action"
          description={
            <pre style={{ margin: 0, fontSize: 12 }}>
              {JSON.stringify(result.pending_action, null, 2)}
            </pre>
          }
          type="warning"
          showIcon
        />
      )}

      {/* 错误列表 */}
      {result.errors.length > 0 && (
        <Alert
          style={{ marginTop: 16 }}
          message={`错误列表 (${result.errors.length})`}
          description={
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              {result.errors.map((err, i) => {
                const tag = getErrorTag(err);
                return (
                  <li key={i} style={{ marginBottom: 4 }}>
                    <Tag color={tag.color} size="small">{tag.label}</Tag>
                    <Text type="danger" style={{ marginLeft: 8 }}>{err}</Text>
                  </li>
                );
              })}
            </ul>
          }
          type="error"
          showIcon
        />
      )}

      {/* 预期 vs 实际 */}
      <ExpectedVsActual expected={result.expected_db_changes} actual={result.db_diff} />

      {/* 声称 vs 现实 */}
      <ClaimComparisonTable claims={result.extracted_claims} dbDiff={result.db_diff} />
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────

export default function Simulation() {
  // -- State --
  const [cases, setCases] = useState<SimulationCase[]>([]);
  const [selectedCaseIds, setSelectedCaseIds] = useState<Set<string>>(new Set());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [agentUrl, setAgentUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const [currentRun, setCurrentRun] = useState<RunStatus | null>(null);
  const [runHistory, setRunHistory] = useState<RunSummary[]>([]);
  const [expandedRowKeys, setExpandedRowKeys] = useState<string[]>([]);

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // -- API Calls --
  const fetchCases = useCallback(async (category?: string) => {
    try {
      setLoading(true);
      const url = category ? `/simulation/cases?category=${category}` : '/simulation/cases';
      const resp = await apiClient.get(url);
      setCases(resp.data.cases || []);
    } catch {
      message.error('加载测试用例失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      const resp = await apiClient.get('/simulation/runs');
      setRunHistory(resp.data.runs || []);
    } catch {
      // 静默失败，历史记录不是关键功能
    }
  }, []);

  const fetchRunStatus = useCallback(async (runId: string) => {
    try {
      const resp = await apiClient.get(`/simulation/run/${runId}`);
      const run: RunStatus = resp.data;
      setCurrentRun(run);

      if (run.status === 'running') {
        setRunning(true);
      } else {
        setRunning(false);
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        // 运行完成，刷新历史
        fetchRuns();
      }
    } catch {
      message.error('查询运行状态失败');
      setRunning(false);
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    }
  }, [fetchRuns]);

  const startPoll = useCallback((runId: string) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    pollTimerRef.current = setInterval(() => {
      fetchRunStatus(runId);
    }, 1000);
  }, [fetchRunStatus]);

  const startRun = async (caseIds: string[] | null) => {
    try {
      setRunning(true);
      const resp = await apiClient.post('/simulation/run', {
        case_ids: caseIds,
        agent_url: agentUrl,
      });
      const { run_id } = resp.data;
      message.success(`测试已启动: ${run_id}`);
      setCurrentRun({ ...resp.data, progress: { current: 0, total: resp.data.total }, results: [] });
      startPoll(run_id);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      message.error(detail || '启动测试失败');
      setRunning(false);
    }
  };

  // -- Effects --
  useEffect(() => {
    let mounted = true;
    const init = async () => {
      await fetchCases();
      if (mounted) await fetchRuns();
    };
    init();
    return () => {
      mounted = false;
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [fetchCases, fetchRuns]);

  // -- Handlers --
  const handleSelectAll = () => setSelectedCaseIds(new Set(cases.map(c => c.case_id)));
  const handleDeselectAll = () => setSelectedCaseIds(new Set());

  const handleCaseToggle = (caseId: string, checked: boolean) => {
    const next = new Set(selectedCaseIds);
    if (checked) next.add(caseId);
    else next.delete(caseId);
    setSelectedCaseIds(next);
  };

  const handleCategoryChange = (value: string | undefined) => {
    setCategoryFilter(value || null);
    fetchCases(value);
  };

  const handleRunSelected = () => {
    if (selectedCaseIds.size === 0) {
      message.warning('请先选择测试用例');
      return;
    }
    startRun(Array.from(selectedCaseIds));
  };

  const handleRunAll = () => startRun(null);

  // -- Render helpers --
  const accuracy = currentRun && currentRun.total > 0
    ? Math.round(((currentRun.passed || 0) / currentRun.total) * 100)
    : 0;

  // -- Columns --
  const resultColumns = [
    {
      title: '用例ID',
      dataIndex: 'case_id',
      width: 120,
    },
    {
      title: '描述',
      dataIndex: 'case_id',
      render: (id: string) => {
        const c = cases.find(x => x.case_id === id);
        return c?.description || id;
      },
    },
    {
      title: '结果',
      dataIndex: 'passed',
      width: 100,
      render: (passed: boolean) => passed
        ? <Tag icon={<CheckCircleOutlined />} color="success">PASS</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="error">FAIL</Tag>,
    },
    {
      title: '延迟',
      dataIndex: 'latency_ms',
      width: 100,
      render: (ms: number) => <Text><ClockCircleOutlined /> {ms}ms</Text>,
    },
    {
      title: '错误类型',
      dataIndex: 'errors',
      render: (errors: string[]) => errors.length > 0
        ? <Space size={4}>{errors.map((e, i) => {
            const type = e.split(':')[0];
            return <Tag key={i} color="error">{type}</Tag>;
          })}</Space>
        : <Text type="secondary">-</Text>,
    },
  ];

  return (
    <div style={{ padding: '0 0 40px' }}>
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <ExperimentOutlined style={{ fontSize: 24, color: '#58a6ff' }} />
            <Title level={3} style={{ margin: 0 }}>Agent 仿真测试平台</Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Input
              placeholder="留空使用当前服务地址"
              value={agentUrl}
              onChange={e => setAgentUrl(e.target.value)}
              style={{ width: 240 }}
              disabled={running}
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={() => fetchCases(categoryFilter || undefined)}
              loading={loading}
            >
              刷新用例
            </Button>
          </Space>
        </Col>
      </Row>

      {/* Main Content */}
      <Row gutter={[24, 24]}>
        {/* Left: Case List */}
        <Col xs={24} lg={8} style={{ position: 'sticky', top: 24, alignSelf: 'start' }}>
          <Card
            title={
              <Space>
                <Text strong>测试用例</Text>
                <Badge count={selectedCaseIds.size} showZero style={{ backgroundColor: '#58a6ff' }} />
                <Text type="secondary">/ {cases.length}</Text>
              </Space>
            }
            extra={
              <Space>
                <Button size="small" onClick={handleSelectAll}>全选</Button>
                <Button size="small" onClick={handleDeselectAll}>全不选</Button>
              </Space>
            }
          >
            <Space style={{ marginBottom: 16 }}>
              <Select
                placeholder="按分类筛选"
                allowClear
                style={{ width: 160 }}
                onChange={handleCategoryChange}
                value={categoryFilter || undefined}
              >
                {CATEGORIES.map(c => (
                  <Option key={c} value={c}>
                    <Tag color={CATEGORY_COLORS[c]}>{c}</Tag>
                  </Option>
                ))}
              </Select>
            </Space>

            <Spin spinning={loading}>
              <div style={{ maxHeight: 600, overflow: 'auto' }}>
                {cases.map(c => (
                  <div
                    key={c.case_id}
                    style={{
                      padding: '10px 12px',
                      borderBottom: '1px solid #30363d',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <Checkbox
                      checked={selectedCaseIds.has(c.case_id)}
                      onChange={e => handleCaseToggle(c.case_id, e.target.checked)}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Text strong>{c.case_id}</Text>
                        <Tag color={CATEGORY_COLORS[c.category] || 'default'}>{c.category}</Tag>
                      </div>
                      <Text type="secondary" style={{ fontSize: 12 }} ellipsis>
                        {c.description}
                      </Text>
                    </div>
                  </div>
                ))}
                {cases.length === 0 && (
                  <Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 40 }}>
                    暂无测试用例
                  </Text>
                )}
              </div>
            </Spin>
          </Card>
        </Col>

        {/* Right: Status + Results */}
        <Col xs={24} lg={16}>
          {/* Status Card */}
          <Card style={{ marginBottom: 24 }}>
            <Row gutter={[24, 16]} align="middle">
              <Col flex="auto">
                {currentRun ? (
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Space>
                      <Text strong>Run:</Text>
                      <Text code>{currentRun.run_id}</Text>
                      <Tag color={currentRun.status === 'running' ? 'processing' : currentRun.status === 'completed' ? 'success' : 'error'}>
                        {currentRun.status}
                      </Tag>
                    </Space>
                    {currentRun.status === 'running' && (
                      <Progress
                        percent={Math.round((currentRun.progress.current / currentRun.progress.total) * 100)}
                        status="active"
                        format={() => `${currentRun.progress.current}/${currentRun.progress.total}`}
                      />
                    )}
                    {currentRun.status === 'completed' && (
                      <Space size={24}>
                        <Text>通过: <Text type="success" strong>{currentRun.passed}</Text></Text>
                        <Text>失败: <Text type="danger" strong>{currentRun.failed}</Text></Text>
                        <Text>准确率: <Text strong>{accuracy}%</Text></Text>
                      </Space>
                    )}
                    {currentRun.error && (
                      <Alert message={currentRun.error} type="error" showIcon />
                    )}
                  </Space>
                ) : (
                  <Text type="secondary">暂无运行记录，点击右侧按钮开始测试</Text>
                )}
              </Col>
              <Col>
                <Space direction="vertical">
                  <Button
                    type="primary"
                    icon={<PlayCircleOutlined />}
                    onClick={handleRunSelected}
                    loading={running}
                    disabled={running || selectedCaseIds.size === 0}
                  >
                    运行选中用例 ({selectedCaseIds.size})
                  </Button>
                  <Button
                    icon={<PlayCircleOutlined />}
                    onClick={handleRunAll}
                    loading={running}
                    disabled={running}
                  >
                    运行全部 ({cases.length})
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* Results Table */}
          {currentRun && currentRun.results.length > 0 && (
            <Card title="测试结果">
              <Table
                rowKey="case_id"
                size="small"
                columns={resultColumns}
                dataSource={currentRun.results}
                pagination={{ pageSize: 10 }}
                expandable={{
                  expandedRowKeys,
                  onExpandedRowsChange: (keys) => setExpandedRowKeys(keys as string[]),
                  expandedRowRender: (record: SimulationResult) => <ResultDetail result={record} />,
                }}
              />
            </Card>
          )}

          {/* Run History */}
          {runHistory.length > 0 && !currentRun && (
            <Card title="历史运行">
              <Table
                rowKey="run_id"
                size="small"
                dataSource={runHistory}
                pagination={false}
                columns={[
                  {
                    title: 'Run ID',
                    dataIndex: 'run_id',
                    render: (run_id: string) => (
                      <Button type="link" onClick={() => fetchRunStatus(run_id)}>
                        {run_id}
                      </Button>
                    ),
                  },
                  {
                    title: '状态',
                    dataIndex: 'status',
                    render: (s: string) => <Tag color={s === 'completed' ? 'success' : s === 'running' ? 'processing' : 'error'}>{s}</Tag>,
                  },
                  { title: '通过', dataIndex: 'passed' },
                  { title: '失败', dataIndex: 'failed' },
                  { title: '时间', dataIndex: 'created_at' },
                ]}
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
