import { useCallback, useEffect, useState } from 'react';
import { App, Table, Button, Modal, Form, Input, DatePicker, Select, Space, message, Dropdown, Card, Alert, Empty } from 'antd';
import { PlusOutlined, BugOutlined, EditOutlined, DeleteOutlined, SearchOutlined, EllipsisOutlined, ClockCircleOutlined, ArrowRightOutlined, RobotOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { listCycles, createCycle, updateCycle, deleteCycle, parseCycle, type CropCycleListItem, type CycleParseResponse } from '../../api/cycles';
import { listTemplates, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';
import { PageShell } from '../../components/PageShell';
import { cardStyle } from '../../styles/theme';
import { buildCycleFormValues } from '../Operations/smartCreateModel';

export default function Cycles() {
  const { modal } = App.useApp();
  const [data, setData] = useState<CropCycleListItem[]>([]);
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [query, setQuery] = useState('');
  const [stage, setStage] = useState<string>();
  const [selectedId, setSelectedId] = useState<number>();
  const [loadError, setLoadError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [smartText, setSmartText] = useState('');
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartResult, setSmartResult] = useState<CycleParseResponse | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = useCallback(async (page: number, pageSize: number) => {
    setLoading(true);
    setLoadError(false);
    try {
      const [cyclesRes, tplRes] = await Promise.all([
        listCycles({ page, page_size: pageSize }),
        listTemplates(),
      ]);
      setData(cyclesRes.items);
      setPagination({ current: page, pageSize, total: cyclesRes.total });
      setTemplates(tplRes.items);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(1, pagination.pageSize); }, [fetchData, pagination.pageSize]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createCycle({ ...values, start_date: values.start_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('创建失败');
    }
  };

  const openEdit = (record: CropCycleListItem) => {
    setSmartText('');
    setSmartResult(null);
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      crop_template_id: templates.find((item) => item.name === record.crop_template_name)?.id,
      start_date: dayjs(record.start_date),
    });
    setModalOpen(true);
  };

  const openCreate = () => {
    setEditingId(null);
    setSmartText('');
    setSmartResult(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleSmartParse = async () => {
    if (!smartText.trim()) {
      message.warning('请输入茬口描述');
      return;
    }
    setSmartLoading(true);
    try {
      const parsed = await parseCycle(smartText.trim());
      setSmartResult(parsed);
      form.setFieldsValue(buildCycleFormValues(parsed));
      message.success('已解析并回填茬口');
    } catch {
      message.error('智能解析失败，请检查 AI 配置或改用手填');
    } finally {
      setSmartLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const values = await form.validateFields();
    try {
      await updateCycle(editingId, { ...values, start_date: values.start_date.format('YYYY-MM-DD') });
      message.success('更新成功');
      setModalOpen(false);
      setEditingId(null);
      form.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteCycle(id);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('删除失败');
    }
  };

  // 接口仅支持分页；筛选明确限定本页，避免把局部命中误报成全量结果。
  const visibleData = data.filter((item) =>
    `${item.name} ${item.crop_template_name ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())
    && (!stage || item.current_stage_name === stage));
  const selected = visibleData.find((item) => item.id === selectedId) ?? visibleData[0];
  const stageOptions = [...new Set(data.map((item) => item.current_stage_name).filter(Boolean))]
    .map((value) => ({ value, label: value }));
  const columns = [
    { title: '种植计划', dataIndex: 'name', width: 270, render: (name: string, record: CropCycleListItem) => (
      <div className="cycle-name"><span className="cycle-number">{String(record.id).padStart(2, '0')}</span>
        <button type="button" aria-pressed={selected?.id === record.id} onClick={() => setSelectedId(record.id)}>{name}</button>
      </div>
    ) },
    { title: '开始日期', dataIndex: 'start_date' },
    { title: '当前阶段', dataIndex: 'current_stage_name', render: (text?: string) => text || '尚未设置' },
    { title: '状态', dataIndex: 'status', render: (status: string) => (
      <span className="cycle-status"><ClockCircleOutlined />{status === 'active' ? '进行中' : status}</span>
    ) },
    { title: '操作', key: 'action', width: 180, fixed: 'right' as const, render: (_: unknown, record: CropCycleListItem) => (
      <Space>
        <Button onClick={() => navigate(`/cycles/${record.id}`)}>查看详情</Button>
        <Dropdown trigger={['click']} menu={{ items: [
          { key: 'edit', label: '编辑茬口', icon: <EditOutlined />, onClick: () => openEdit(record) },
          { key: 'delete', label: '删除茬口', icon: <DeleteOutlined />, danger: true, onClick: () => modal.confirm({
            title: '确认删除', content: `删除“${record.name}”？`, okText: '删除', cancelText: '取消',
            okButtonProps: { danger: true }, onOk: () => handleDelete(record.id),
          }) },
        ] }}>
          <Button type="text" aria-label={`更多操作：${record.name}`} icon={<EllipsisOutlined />} />
        </Dropdown>
      </Space>
    ) },
  ];

  return (
    <PageShell
      title="种植周期"
      description="查看种植进展，管理每一季的农事。"
      actions={<Button type="primary" aria-label="新建茬口" icon={<PlusOutlined aria-hidden />} onClick={openCreate}>新建茬口</Button>}
    >
      <div className="cycles-toolbar">
        <span>全部周期 <strong>{pagination.total}</strong></span>
        <div className="cycles-toolbar__filters">
          <Input aria-label="搜索本页种植计划" placeholder="搜索本页种植计划" prefix={<SearchOutlined />} allowClear value={query} onChange={(event) => setQuery(event.target.value)} />
          <Select aria-label="筛选本页阶段" placeholder="本页阶段" allowClear value={stage} onChange={setStage} options={stageOptions} />
          <Button aria-label="接口调试" title="接口调试" icon={<BugOutlined />} onClick={() => setDebugOpen(true)} />
        </div>
      </div>
      {loadError && <Alert type="error" showIcon message="种植周期加载失败" description="请检查网络后重试。错误代码：CYCLES_LOAD_FAILED" action={<Button onClick={() => fetchData(pagination.current, pagination.pageSize)}>重试</Button>} />}
      <Table
        rowKey="id"
        className="cycles-table"
        dataSource={loadError ? [] : visibleData}
        rowClassName={(record) => record.id === selected?.id ? 'cycle-row--selected' : ''}
        locale={{ emptyText: <Empty description={query || stage ? '本页没有匹配的种植计划，请调整筛选' : '暂无种植周期，点击新建茬口开始'} /> }}
        columns={columns}
        loading={loading}
        size="large"
        scroll={{ x: 950 }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
          showTotal: (count) => `共 ${count} 条`,
        }}
        onChange={(p) => { setQuery(''); setStage(undefined); fetchData(p.current ?? 1, p.pageSize ?? pagination.pageSize); }}
      />

      {selected && !loadError && (
        <aside className="cycle-summary" aria-label="选中种植计划摘要">
          <strong>{selected.name}</strong><span>当前阶段 {selected.current_stage_name || '尚未设置'}</span>
          <span>开始于 {selected.start_date}</span>
          <Button type="link" onClick={() => navigate(`/cycles/${selected.id}`)}>查看种植详情 <ArrowRightOutlined /></Button>
        </aside>
      )}

      <Modal okText="保存" cancelText="取消" title={editingId !== null ? '编辑茬口' : '新建茬口'} open={modalOpen} onOk={editingId !== null ? handleUpdate : handleCreate} onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }}>
        {editingId === null && (
          <Card size="small" title={<span><RobotOutlined /> 智能茬口</span>} style={{ ...cardStyle, marginBottom: 16 }}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={smartText}
                onChange={(event) => setSmartText(event.target.value)}
                onPressEnter={handleSmartParse}
                placeholder="例如：今年 4 月 1 日在东棚种一茬 8424 西瓜"
              />
              <Button type="primary" loading={smartLoading} onClick={handleSmartParse}>解析回填</Button>
            </Space.Compact>
            {smartResult && (
              <Alert
                style={{ marginTop: 12 }}
                type="info"
                showIcon
                message="解析结果已填入下方表单，确认无误后再创建茬口。"
                description={`${smartResult.name} · ${smartResult.start_date}${smartResult.field_name ? ` · ${smartResult.field_name}` : ''}`}
              />
            )}
          </Card>
        )}
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="crop_template_id" label="作物模板" rules={[{ required: true }]}>
            <Select options={templates.map((t) => ({ value: t.id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="start_date" label="开始日期" rules={[{ required: true }]}><DatePicker placeholder="选择开始日期" style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="field_name" label="地块名称"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/cycles" />
    </PageShell>
  );
}
