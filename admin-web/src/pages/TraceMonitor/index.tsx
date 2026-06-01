import { useEffect, useState, useCallback } from 'react';
import {
  Input,
  Button,
  Space,
  message,
  Modal,
  Drawer,
  DatePicker,
  Typography,
  Tag,
  Pagination,
} from 'antd';
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import {
  listTraces,
  getTimeline,
  deleteTracesBefore,
  type TraceRecord,
  type TraceTimeline,
  type TraceNodeDetail,
} from '../../api/admin';
import GanttTimeline from '../../components/GanttTimeline';
import type { GanttNode } from '../../components/GanttTimeline/types';
import { getNodeLabel } from '../../constants/trace';
import SkillOutputFormatter from '../../components/SkillOutputFormatter';

const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';

interface TraceItem {
  request_id: string;
  session_id: string | null;
  farm_id: number;
  node_count: number;
  total_duration_ms: number;
  created_at: string;
  timeline: TraceTimeline | null;
  timelineLoading: boolean;
}

export default function TraceMonitor() {
  const [items, setItems] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    request_id: '',
    session_id: '',
    farm_id: '',
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<TraceNodeDetail | null>(null);
  const [cleanupDate, setCleanupDate] = useState<Dayjs | null>(null);
  const [cleanupModalOpen, setCleanupModalOpen] = useState(false);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const fetchData = useCallback(
    async (p = page, ps = pageSize) => {
      setLoading(true);
      try {
        const params: Record<string, unknown> = {
          limit: ps,
          offset: (p - 1) * ps,
        };
        if (filters.request_id.trim()) params.request_id = filters.request_id.trim();
        if (filters.session_id.trim()) params.session_id = filters.session_id.trim();
        if (filters.farm_id.trim()) params.farm_id = Number(filters.farm_id.trim());

        const res = await listTraces(params);
        const aggregated = aggregateTraces(res.items);
        setItems(aggregated);
        setTotal(res.total);
        setPage(p);
        setPageSize(ps);
        setExpandedCards(new Set());
      } catch {
        message.error('加载 Trace 列表失败');
      } finally {
        setLoading(false);
      }
    },
    [filters, page, pageSize]
  );

  useEffect(() => {
    fetchData();
  }, []);

  const aggregateTraces = (records: TraceRecord[]): TraceItem[] => {
    const groups = new Map<string, TraceRecord[]>();
    records.forEach((item) => {
      const arr = groups.get(item.request_id) || [];
      arr.push(item);
      groups.set(item.request_id, arr);
    });

    return Array.from(groups.entries()).map(([request_id, records]) => ({
      request_id,
      session_id: records[0].session_id,
      farm_id: records[0].farm_id,
      node_count: records.length,
      total_duration_ms: records.reduce((s, r) => s + (r.duration_ms || 0), 0),
      created_at: records[0].created_at,
      timeline: null,
      timelineLoading: true,
    }));
  };

  const loadTimeline = async (requestId: string) => {
    try {
      const res = await getTimeline(requestId);
      setItems((prev) =>
        prev.map((item) =>
          item.request_id === requestId
            ? { ...item, timeline: res, timelineLoading: false }
            : item
        )
      );
    } catch {
      setItems((prev) =>
        prev.map((item) =>
          item.request_id === requestId
            ? { ...item, timeline: null, timelineLoading: false }
            : item
        )
      );
    }
  };

  const handleNodeClick = (
    requestId: string,
    _roundIndex: number,
    _nodeIndex: number,
    nodeData: GanttNode
  ) => {
    const detail: TraceNodeDetail = {
      id: 0,
      request_id: requestId,
      round_index: _roundIndex,
      node_type: nodeData.node_type,
      node_name: nodeData.node_name,
      input_data: nodeData.input_data ?? null,
      output_data: nodeData.output_data ?? null,
      duration_ms: nodeData.duration_ms,
      token_usage: null,
      status: nodeData.status,
      error_message: nodeData.error_message ?? null,
      start_time: nodeData.start_time,
      end_time: null,
    };
    setNodeDetail(detail);
    setDrawerOpen(true);
  };

  const formatJson = (raw: string | null): string => {
    if (!raw) return '';
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  };

  const handleCleanup = async () => {
    if (!cleanupDate) {
      message.warning('请选择清理日期');
      return;
    }
    setCleanupModalOpen(true);
  };

  const confirmCleanup = async () => {
    if (!cleanupDate) return;
    try {
      const before = cleanupDate.format('YYYY-MM-DD');
      const res = await deleteTracesBefore(before);
      message.success(`已清理 ${res.deleted} 条历史记录`);
      setCleanupModalOpen(false);
      setCleanupDate(null);
      fetchData(1);
    } catch {
      message.error('清理失败');
    }
  };

  const toggleCard = (requestId: string) => {
    setExpandedCards((prev) => {
      const next = new Set(prev);
      if (next.has(requestId)) {
        next.delete(requestId);
      } else {
        next.add(requestId);
        const item = items.find((i) => i.request_id === requestId);
        if (item && !item.timeline) {
          loadTimeline(requestId);
        }
      }
      return next;
    });
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        链路追踪
      </Typography.Title>

      {/* 筛选区 */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Request ID"
          value={filters.request_id}
          onChange={(e) => setFilters((f) => ({ ...f, request_id: e.target.value }))}
          style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Input
          placeholder="Session ID"
          value={filters.session_id}
          onChange={(e) => setFilters((f) => ({ ...f, session_id: e.target.value }))}
          style={{ width: 200, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Input
          placeholder="Farm ID"
          value={filters.farm_id}
          onChange={(e) => setFilters((f) => ({ ...f, farm_id: e.target.value }))}
          style={{ width: 120, background: CARD, borderColor: BORDER, color: TEXT }}
          allowClear
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={() => fetchData(1)} loading={loading}>
          查询
        </Button>
      </Space>

      {/* Trace 列表 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 24 }}>
        {items.map((item) => (
          <div
            key={item.request_id}
            style={{
              background: CARD,
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              overflow: 'hidden',
            }}
          >
            {/* Trace 头部信息 - 可点击折叠/展开 */}
            <div
              onClick={() => toggleCard(item.request_id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '12px 16px',
                borderBottom: expandedCards.has(item.request_id)
                  ? `1px solid ${BORDER}`
                  : 'none',
                gap: 24,
                fontSize: 13,
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
            >
              <span>
                <span style={{ color: TEXT_DIM }}>Request ID: </span>
                <span style={{ fontFamily: 'monospace', color: ACCENT }}>
                  {item.request_id.slice(0, 16)}...
                </span>
              </span>
              {item.session_id && (
                <span>
                  <span style={{ color: TEXT_DIM }}>Session: </span>
                  <span style={{ fontFamily: 'monospace', color: TEXT_DIM }}>
                    {item.session_id.slice(0, 16)}...
                  </span>
                </span>
              )}
              <span>
                <span style={{ color: TEXT_DIM }}>Farm: </span>
                <span style={{ color: TEXT }}>{item.farm_id}</span>
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>节点: </span>
                <span style={{ color: TEXT }}>{item.node_count}</span>
              </span>
              <span>
                <span style={{ color: TEXT_DIM }}>耗时: </span>
                <span style={{ color: TEXT }}>{item.total_duration_ms}ms</span>
              </span>
              <span style={{ marginLeft: 'auto', color: TEXT_DIM, fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{new Date(item.created_at).toLocaleString('zh-CN')}</span>
                <span style={{ color: ACCENT }}>
                  {expandedCards.has(item.request_id) ? '收起 ▲' : '展开 ▼'}
                </span>
              </span>
            </div>

            {/* Gantt 图 - 展开时显示 */}
            {expandedCards.has(item.request_id) && (
            <div style={{ padding: 16 }}>
              {item.timelineLoading ? (
                <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 24 }}>
                  加载 Timeline...
                </div>
              ) : item.timeline ? (
                <GanttTimeline
                  rounds={item.timeline.rounds.map((r) => ({
                    round_index: r.round_index,
                    nodes: r.nodes.map((n) => ({
                      node_type: n.node_type,
                      node_name: n.node_name,
                      duration_ms: n.duration_ms,
                      status: n.status,
                      start_time: n.start_time,
                      input_data: n.input_data,
                      output_data: n.output_data,
                      error_message: n.error_message,
                    })),
                  }))}
                  onNodeClick={(roundIdx, nodeIdx, node) =>
                    handleNodeClick(item.request_id, roundIdx, nodeIdx, node)
                  }
                />
              ) : (
                <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 24 }}>
                  <div style={{ marginBottom: 8 }}>暂无 Timeline 数据（可能该 Trace 已过期或未记录链路）</div>
                  <Button size="small" onClick={() => loadTimeline(item.request_id)}>
                    重试加载
                  </Button>
                </div>
              )}
            </div>
            )}
          </div>
        ))}
      </div>

      {/* 分页 */}
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
        <Pagination
          current={page}
          pageSize={pageSize}
          total={total}
          showSizeChanger
          pageSizeOptions={[10, 20, 50]}
          onChange={(p, ps) => fetchData(p, ps)}
          style={{ color: TEXT }}
        />
      </div>

      {/* 清理操作 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: 16,
          background: CARD,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
        }}
      >
        <span style={{ color: TEXT_DIM }}>清理历史数据：</span>
        <DatePicker
          placeholder="选择日期"
          value={cleanupDate}
          onChange={setCleanupDate}
          style={{ width: 200, background: CARD, borderColor: BORDER }}
        />
        <Button danger icon={<ClearOutlined />} onClick={handleCleanup}>
          清理历史
        </Button>
      </div>

      {/* 确认弹窗 */}
      <Modal
        title="确认清理"
        open={cleanupModalOpen}
        onOk={confirmCleanup}
        onCancel={() => setCleanupModalOpen(false)}
        okText="确认清理"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <p style={{ color: TEXT }}>
          确定要清理 <strong>{cleanupDate?.format('YYYY-MM-DD')}</strong> 之前的所有 Trace 记录吗？
        </p>
        <p style={{ color: TEXT_DIM }}>此操作不可恢复。</p>
      </Modal>

      {/* 节点详情 Drawer */}
      <Drawer
        title="节点详情"
        placement="right"
        width={640}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
      >
        {nodeDetail ? (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <Tag color={nodeDetail.status === 'success' ? 'success' : 'error'}>
                {nodeDetail.status}
              </Tag>
              <Tag color="processing">{getNodeLabel(nodeDetail.node_type)}</Tag>
              <span style={{ color: TEXT_DIM }}>
                {nodeDetail.duration_ms?.toLocaleString() ?? '-'} ms
              </span>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>节点名称</div>
              <div style={{ fontSize: 15, fontWeight: 500 }}>{nodeDetail.node_name}</div>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>Request ID</div>
              <div style={{ fontFamily: 'monospace', fontSize: 12 }}>{nodeDetail.request_id}</div>
            </div>
            {nodeDetail.start_time && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>开始时间</div>
                <div>{new Date(nodeDetail.start_time).toLocaleString('zh-CN')}</div>
              </div>
            )}
            {nodeDetail.error_message && (
              <div>
                <div style={{ color: '#ff4d4f', marginBottom: 4, fontSize: 12 }}>错误信息</div>
                <pre style={{
                  backgroundColor: '#2a1215',
                  padding: 12,
                  borderRadius: 6,
                  border: '1px solid #58181c',
                  color: '#ff4d4f',
                  fontSize: 12,
                  margin: 0,
                  whiteSpace: 'pre-wrap',
                }}>
                  {nodeDetail.error_message}
                </pre>
              </div>
            )}
            {nodeDetail.input_data && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输入数据</div>
                <pre style={{
                  backgroundColor: '#161b22',
                  padding: 12,
                  borderRadius: 6,
                  border: '1px solid #30363d',
                  fontSize: 12,
                  margin: 0,
                  maxHeight: 300,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                }}>
                  {formatJson(nodeDetail.input_data)}
                </pre>
              </div>
            )}
            {nodeDetail.output_data && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4, fontSize: 12 }}>输出数据</div>
                {nodeDetail.node_type === 'skill_call' ? (
                  <SkillOutputFormatter outputData={nodeDetail.output_data} />
                ) : (
                  <pre style={{
                    backgroundColor: '#161b22',
                    padding: 12,
                    borderRadius: 6,
                    border: '1px solid #30363d',
                    fontSize: 12,
                    margin: 0,
                    maxHeight: 300,
                    overflow: 'auto',
                    whiteSpace: 'pre-wrap',
                  }}>
                    {formatJson(nodeDetail.output_data)}
                  </pre>
                )}
              </div>
            )}
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
