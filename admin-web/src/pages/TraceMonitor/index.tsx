import { useEffect, useState, useCallback } from 'react';
import {
  Table,
  Button,
  Input,
  Space,
  message,
  Modal,
  Drawer,
  DatePicker,
  Typography,
  Tag,
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
import type { GanttRound } from '../../components/GanttTimeline/types';

const BG = '#0d1117';
const CARD = '#161b22';
const BORDER = '#30363d';
const TEXT = '#e6edf3';
const TEXT_DIM = '#8b949e';
const ACCENT = '#58a6ff';

interface AggregatedTrace {
  request_id: string;
  farm_id: number;
  node_count: number;
  total_duration_ms: number;
  created_at: string;
}

interface ExpandedState {
  [requestId: string]: {
    timeline: TraceTimeline | null;
    loading: boolean;
  };
}

export default function TraceMonitor() {
  const [traces, setTraces] = useState<AggregatedTrace[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [filters, setFilters] = useState({
    request_id: '',
    session_id: '',
    farm_id: '',
  });
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [nodeDetail, setNodeDetail] = useState<TraceNodeDetail | null>(null);
  const [cleanupDate, setCleanupDate] = useState<Dayjs | null>(null);
  const [cleanupModalOpen, setCleanupModalOpen] = useState(false);

  const fetchData = useCallback(
    async (page = pagination.current, pageSize = pagination.pageSize) => {
      setLoading(true);
      try {
        const params: Record<string, unknown> = {
          limit: pageSize,
          offset: (page - 1) * pageSize,
        };
        if (filters.request_id.trim()) params.request_id = filters.request_id.trim();
        if (filters.session_id.trim()) params.session_id = filters.session_id.trim();
        if (filters.farm_id.trim()) params.farm_id = Number(filters.farm_id.trim());

        const res = await listTraces(params);
        const aggregated = aggregateTraces(res.items);
        setTraces(aggregated);
        setPagination({ current: page, pageSize, total: res.total });
      } catch {
        message.error('加载 Trace 列表失败');
      } finally {
        setLoading(false);
      }
    },
    [filters, pagination.current, pagination.pageSize]
  );

  useEffect(() => {
    fetchData();
  }, []);

  const aggregateTraces = (items: TraceRecord[]): AggregatedTrace[] => {
    const groups = new Map<string, TraceRecord[]>();
    items.forEach((item) => {
      const arr = groups.get(item.request_id) || [];
      arr.push(item);
      groups.set(item.request_id, arr);
    });

    return Array.from(groups.entries()).map(([request_id, records]) => ({
      request_id,
      farm_id: records[0].farm_id,
      node_count: records.length,
      total_duration_ms: records.reduce((sum, r) => sum + (r.duration_ms || 0), 0),
      created_at: records[0].created_at,
    }));
  };

  const handleExpand = async (expanded: boolean, record: AggregatedTrace) => {
    if (!expanded) return;
    setExpanded((prev) => ({
      ...prev,
      [record.request_id]: { timeline: null, loading: true },
    }));
    try {
      const timelineRes = await getTimeline(record.request_id);
      const timeline = timelineRes;
      setExpanded((prev) => ({
        ...prev,
        [record.request_id]: { timeline, loading: false },
      }));
    } catch {
      message.error('加载 Timeline 失败');
      setExpanded((prev) => ({
        ...prev,
        [record.request_id]: { timeline: null, loading: false },
      }));
    }
  };

  const handleNodeClick = async (requestId: string, roundIndex: number, nodeIndex: number) => {
    const timeline = expanded[requestId]?.timeline;
    if (!timeline) return;
    const node = timeline.rounds[roundIndex]?.nodes[nodeIndex];
    if (!node) return;

    setDrawerOpen(true);
    setDrawerLoading(true);
    setNodeDetail(null);

    try {
      // 通过 node_name + node_type + round_index 找到对应节点 id
      // 后端 getNodeDetail 需要 nodeId，但 Gantt 组件没有传 id
      // 这里我们直接从 timeline 数据展示，不调用 getNodeDetail（缺少 nodeId）
      // 如果需要完整详情，需要后端在 timeline 接口中返回 node id
      // 暂时用 timeline 中的数据构造一个简化版详情
      const detail: TraceNodeDetail = {
        id: 0,
        request_id: requestId,
        round_index: roundIndex,
        node_type: node.node_type,
        node_name: node.node_name,
        input_data: node.input_data,
        output_data: node.output_data,
        duration_ms: node.duration_ms,
        token_usage: node.token_usage ? JSON.stringify(node.token_usage) : null,
        status: node.status,
        error_message: node.error_message,
        start_time: node.start_time,
        end_time: null,
      };
      setNodeDetail(detail);
    } finally {
      setDrawerLoading(false);
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

  const columns = [
    {
      title: 'Request ID',
      dataIndex: 'request_id',
      render: (v: string) => (
        <span style={{ fontFamily: 'monospace', color: ACCENT }}>{v.slice(0, 8)}</span>
      ),
    },
    { title: 'Farm ID', dataIndex: 'farm_id', width: 80 },
    { title: '节点数', dataIndex: 'node_count', width: 80 },
    {
      title: '总耗时 (ms)',
      dataIndex: 'total_duration_ms',
      width: 120,
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
    },
  ];

  const expandedRowRender = (record: AggregatedTrace) => {
    const state = expanded[record.request_id];
    if (!state || state.loading) {
      return (
        <div style={{ padding: 24, textAlign: 'center', color: TEXT_DIM }}>加载中...</div>
      );
    }
    if (!state.timeline || state.timeline.rounds.length === 0) {
      return (
        <div style={{ padding: 24, textAlign: 'center', color: TEXT_DIM }}>暂无数据</div>
      );
    }

    const rounds: GanttRound[] = state.timeline.rounds.map((r) => ({
      round_index: r.round_index,
      nodes: r.nodes.map((n) => ({
        node_type: n.node_type,
        node_name: n.node_name,
        duration_ms: n.duration_ms,
        status: n.status,
        start_time: n.start_time,
      })),
    }));

    return (
      <div style={{ padding: 16, backgroundColor: BG, borderRadius: 8 }}>
        <GanttTimeline
          rounds={rounds}
          onNodeClick={(roundIdx, nodeIdx) =>
            handleNodeClick(record.request_id, roundIdx, nodeIdx)
          }
        />
      </div>
    );
  };

  return (
    <div>
      <Typography.Title level={4} style={{ color: TEXT, marginBottom: 16 }}>
        链路追踪
      </Typography.Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="Request ID"
          value={filters.request_id}
          onChange={(e) => setFilters((f) => ({ ...f, request_id: e.target.value }))}
          style={{ width: 200 }}
          allowClear
        />
        <Input
          placeholder="Session ID"
          value={filters.session_id}
          onChange={(e) => setFilters((f) => ({ ...f, session_id: e.target.value }))}
          style={{ width: 200 }}
          allowClear
        />
        <Input
          placeholder="Farm ID"
          value={filters.farm_id}
          onChange={(e) => setFilters((f) => ({ ...f, farm_id: e.target.value }))}
          style={{ width: 120 }}
          allowClear
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={() => fetchData(1)}>
          查询
        </Button>
      </Space>

      <Table
        rowKey="request_id"
        dataSource={traces}
        columns={columns}
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
        }}
        onChange={(p) => fetchData(p.current, p.pageSize)}
        expandable={{
          expandedRowRender,
          onExpand: handleExpand,
        }}
        style={{ marginBottom: 24 }}
      />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: 16,
          backgroundColor: CARD,
          border: `1px solid ${BORDER}`,
          borderRadius: 8,
        }}
      >
        <span style={{ color: TEXT_DIM }}>清理历史数据：</span>
        <DatePicker
          placeholder="选择日期"
          value={cleanupDate}
          onChange={setCleanupDate}
          style={{ width: 200 }}
        />
        <Button danger icon={<ClearOutlined />} onClick={handleCleanup}>
          清理历史
        </Button>
      </div>

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

      <Drawer
        title="节点详情"
        placement="right"
        width={600}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        styles={{
          body: { backgroundColor: BG, color: TEXT },
          header: { backgroundColor: CARD, color: TEXT, borderBottom: `1px solid ${BORDER}` },
        }}
      >
        {drawerLoading ? (
          <div style={{ color: TEXT_DIM }}>加载中...</div>
        ) : nodeDetail ? (
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4 }}>节点类型</div>
              <Tag color="blue">{nodeDetail.node_type}</Tag>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4 }}>节点名称</div>
              <div>{nodeDetail.node_name}</div>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4 }}>状态</div>
              <Tag color={nodeDetail.status === 'success' ? 'success' : 'error'}>
                {nodeDetail.status}
              </Tag>
            </div>
            <div>
              <div style={{ color: TEXT_DIM, marginBottom: 4 }}>耗时</div>
              <div>{nodeDetail.duration_ms?.toLocaleString() ?? '-'} ms</div>
            </div>
            {nodeDetail.error_message && (
              <div>
                <div style={{ color: '#ff4d4f', marginBottom: 4 }}>错误信息</div>
                <div style={{ color: '#ff4d4f' }}>{nodeDetail.error_message}</div>
              </div>
            )}
            {nodeDetail.input_data && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4 }}>输入数据</div>
                <pre
                  style={{
                    backgroundColor: CARD,
                    padding: 12,
                    borderRadius: 4,
                    overflow: 'auto',
                    maxHeight: 300,
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  {nodeDetail.input_data}
                </pre>
              </div>
            )}
            {nodeDetail.output_data && (
              <div>
                <div style={{ color: TEXT_DIM, marginBottom: 4 }}>输出数据</div>
                <pre
                  style={{
                    backgroundColor: CARD,
                    padding: 12,
                    borderRadius: 4,
                    overflow: 'auto',
                    maxHeight: 300,
                    border: `1px solid ${BORDER}`,
                  }}
                >
                  {nodeDetail.output_data}
                </pre>
              </div>
            )}
          </Space>
        ) : null}
      </Drawer>
    </div>
  );
}
