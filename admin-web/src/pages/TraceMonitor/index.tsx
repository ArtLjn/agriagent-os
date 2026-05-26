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

const BG = '#0d1117';
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

        // 自动加载每个 trace 的 timeline
        for (const item of aggregated) {
          loadTimeline(item.request_id);
        }
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

  const handleNodeClick = (requestId: string, roundIndex: number, nodeIndex: number) => {
    const item = items.find((i) => i.request_id === requestId);
    if (!item?.timeline) return;
    const node = item.timeline.rounds[roundIndex]?.nodes[nodeIndex];
    if (!node) return;

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
    setDrawerOpen(true);
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
            {/* Trace 头部信息 */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '12px 16px',
                borderBottom: `1px solid ${BORDER}`,
                gap: 24,
                fontSize: 13,
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
              <span style={{ marginLeft: 'auto', color: TEXT_DIM, fontSize: 12 }}>
                {new Date(item.created_at).toLocaleString('zh-CN')}
              </span>
            </div>

            {/* Gantt 图 */}
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
                  onNodeClick={(roundIdx, nodeIdx) =>
                    handleNodeClick(item.request_id, roundIdx, nodeIdx)
                  }
                />
              ) : (
                <div style={{ color: TEXT_DIM, textAlign: 'center', padding: 24 }}>
                  暂无 Timeline 数据
                </div>
              )}
            </div>
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
        width={600}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        styles={{
          body: { backgroundColor: BG, color: TEXT },
          header: { backgroundColor: CARD, color: TEXT, borderBottom: `1px solid ${BORDER}` },
        }}
      >
        {nodeDetail ? (
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
                    fontSize: 12,
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
                    fontSize: 12,
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
