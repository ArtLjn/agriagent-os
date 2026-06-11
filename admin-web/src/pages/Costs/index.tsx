import { useCallback, useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, DatePicker, Select, Space, Card, Row, Col, Statistic, message, Tag, Alert } from 'antd';
import { PlusOutlined, BugOutlined, DollarOutlined, RiseOutlined, FallOutlined, RobotOutlined } from '@ant-design/icons';
import { listRecords, createRecord, parseCostRecord, getCycleProfit, getYearlySummary, type CostRecord, type CostParseResponse, type CycleProfit, type YearlySummary } from '../../api/costs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';
import { MetricCard, PageShell, Toolbar } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';
import { buildCostCreatePayload, buildCostFormValues } from './costSmartFill';

export default function Costs() {
  const [data, setData] = useState<CostRecord[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [smartText, setSmartText] = useState('');
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartResult, setSmartResult] = useState<CostParseResponse | null>(null);
  const [form] = Form.useForm();
  const [profit, setProfit] = useState<CycleProfit | null>(null);
  const [yearly, setYearly] = useState<YearlySummary | null>(null);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = useCallback(async (page: number, pageSize: number) => {
    setLoading(true);
    try {
      const [recordsRes, cyclesRes] = await Promise.all([
        listRecords(selectedCycle ? { cycle_id: selectedCycle, page, size: pageSize } : { page, size: pageSize }),
        listCycles(),
      ]);
      setData(recordsRes.items);
      setPagination({ current: page, pageSize, total: recordsRes.total });
      setCycles(cyclesRes.items);
      if (selectedCycle) {
        const profitRes = await getCycleProfit(selectedCycle);
        setProfit(profitRes);
      } else {
        setProfit(null);
      }
      const year = new Date().getFullYear();
      const yearlyRes = await getYearlySummary(year);
      setYearly(yearlyRes);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, [selectedCycle]);

  useEffect(() => { fetchData(1, pagination.pageSize); }, [fetchData, pagination.pageSize]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createRecord(buildCostCreatePayload(values));
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('创建失败');
    }
  };

  const openCreateModal = () => {
    setSmartText('');
    setSmartResult(null);
    form.resetFields();
    if (selectedCycle) form.setFieldsValue({ cycle_id: selectedCycle });
    setModalOpen(true);
  };

  const handleSmartParse = async () => {
    if (!smartText.trim()) {
      message.warning('请输入一段记账描述');
      return;
    }
    setSmartLoading(true);
    try {
      const parsed = await parseCostRecord(smartText.trim());
      setSmartResult(parsed);
      form.setFieldsValue({
        ...buildCostFormValues(parsed),
        cycle_id: undefined,
      });
      message.success('已解析并回填表单');
    } catch {
      message.error('智能解析失败，请检查 AI 配置或改用手填');
    } finally {
      setSmartLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '类型',
      dataIndex: 'record_type',
      render: (t: string) => (
        <Tag color={t === 'cost' ? 'red' : 'green'}>{t === 'cost' ? '支出' : '收入'}</Tag>
      ),
    },
    { title: '分类', dataIndex: 'category' },
    { title: '金额', dataIndex: 'amount', render: (value: string) => `¥ ${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}` },
    { title: '日期', dataIndex: 'record_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
  ];

  return (
    <PageShell
      title="成本记账"
      description="汇总年度收入支出，并按茬口查看利润表现。"
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}><MetricCard accent={palette.danger}><Statistic title="年度总支出" value={yearly?.total_cost ?? '--'} precision={2} prefix={<FallOutlined />} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.success}><Statistic title="年度总收入" value={yearly?.total_income ?? '--'} precision={2} prefix={<RiseOutlined />} /></MetricCard></Col>
        <Col xs={24} md={8}>
          <MetricCard accent={yearly && Number(yearly.net_profit) >= 0 ? palette.success : palette.danger}>
            <Statistic title="年度净利润" value={yearly?.net_profit ?? '--'} precision={2}
              prefix={<DollarOutlined />}
              valueStyle={{ color: yearly && Number(yearly.net_profit) >= 0 ? palette.success : palette.danger }} />
          </MetricCard>
        </Col>
      </Row>

      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>新增记录</Button>
            <Select placeholder="按茬口筛选" allowClear style={{ width: 220 }} value={selectedCycle}
              onChange={(v) => setSelectedCycle(v)} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
            <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
          </>
        )}
        right={<span style={{ color: palette.textMuted, fontSize: 13 }}>共 {pagination.total} 条记录</span>}
      />

      {profit && (
        <Card size="small" style={{ ...cardStyle, marginBottom: 16 }}>
          <Space wrap>
            <span>周期支出: ¥ {Number(profit.total_cost).toLocaleString('zh-CN')}</span>
            <span>周期收入: ¥ {Number(profit.total_income).toLocaleString('zh-CN')}</span>
            <span>净利润: <strong style={{ color: Number(profit.net_profit) >= 0 ? palette.success : palette.danger }}>¥ {Number(profit.net_profit).toLocaleString('zh-CN')}</strong></span>
          </Space>
        </Card>
      )}

      <Table
        rowKey="id"
        dataSource={data}
        columns={columns}
        loading={loading}
        size="small"
        scroll={{ x: 760 }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
          showTotal: (count) => `共 ${count} 条`,
        }}
        onChange={(p) => fetchData(p.current ?? 1, p.pageSize ?? pagination.pageSize)}
      />

      <Modal
        title="新增记录"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        width={640}
      >
        <Card
          size="small"
          title={<span><RobotOutlined /> 智能记账</span>}
          style={{ ...cardStyle, marginBottom: 16 }}
        >
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={smartText}
              onChange={(event) => setSmartText(event.target.value)}
              onPressEnter={handleSmartParse}
              placeholder="例如：今天买复合肥 128.5 元，记到春季西瓜"
            />
            <Button type="primary" loading={smartLoading} onClick={handleSmartParse}>解析回填</Button>
          </Space.Compact>
          {smartResult && (
            <Alert
              style={{ marginTop: 12 }}
              type="info"
              showIcon
              message="解析结果已填入下方表单，确认无误后再创建记录。"
              description={`${smartResult.record_type === 'income' ? '收入' : '支出'} · ${smartResult.category} · ¥ ${smartResult.amount} · ${smartResult.record_date}`}
            />
          )}
        </Card>
        <Form form={form} layout="vertical">
          <Form.Item name="record_type" label="类型" rules={[{ required: true }]}>
            <Select options={[{ value: 'cost', label: '支出' }, { value: 'income', label: '收入' }]} />
          </Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="amount" label="金额" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={0} precision={2} />
          </Form.Item>
          <Form.Item name="record_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="cycle_id" label="关联茬口">
            <Select allowClear options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="record_subtype" label="赊账标记">
            <Select allowClear options={[{ value: '赊账', label: '赊账 / 未结' }]} />
          </Form.Item>
          <Form.Item name="counterparty" label="赊账对象"><Input /></Form.Item>
          <Form.Item name="due_date" label="到期日"><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="note" label="备注"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/costs" />
    </PageShell>
  );
}
