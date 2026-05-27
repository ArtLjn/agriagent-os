import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, DatePicker, Select, Space, Card, Row, Col, Statistic, message } from 'antd';
import { PlusOutlined, BugOutlined } from '@ant-design/icons';
import { listRecords, createRecord, getCycleProfit, getYearlySummary, type CostRecord, type CycleProfit, type YearlySummary } from '../../api/costs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';

export default function Costs() {
  const [data, setData] = useState<CostRecord[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [form] = Form.useForm();
  const [profit, setProfit] = useState<CycleProfit | null>(null);
  const [yearly, setYearly] = useState<YearlySummary | null>(null);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = async (page = pagination.current, pageSize = pagination.pageSize) => {
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
      }
      const year = new Date().getFullYear();
      const yearlyRes = await getYearlySummary(year);
      setYearly(yearlyRes);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [selectedCycle]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createRecord({ ...values, amount: String(values.amount), record_date: values.record_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '类型', dataIndex: 'record_type', render: (t: string) => t === 'cost' ? '支出' : '收入' },
    { title: '分类', dataIndex: 'category' },
    { title: '金额', dataIndex: 'amount' },
    { title: '日期', dataIndex: 'record_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}><Card><Statistic title="年度总支出" value={yearly?.total_cost ?? '--'} precision={2} /></Card></Col>
        <Col span={8}><Card><Statistic title="年度总收入" value={yearly?.total_income ?? '--'} precision={2} /></Card></Col>
        <Col span={8}>
          <Card>
            <Statistic title="年度净利润" value={yearly?.net_profit ?? '--'} precision={2}
              valueStyle={{ color: yearly && Number(yearly.net_profit) >= 0 ? '#3f8600' : '#cf1322' }} />
          </Card>
        </Col>
      </Row>

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增记录</Button>
        <Select placeholder="按茬口筛选" allowClear style={{ width: 200 }} value={selectedCycle}
          onChange={(v) => setSelectedCycle(v)} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>

      {profit && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space>
            <span>周期支出: {profit.total_cost}</span>
            <span>周期收入: {profit.total_income}</span>
            <span>净利润: <strong style={{ color: Number(profit.net_profit) >= 0 ? '#3f8600' : '#cf1322' }}>{profit.net_profit}</strong></span>
          </Space>
        </Card>
      )}

      <Table
        rowKey="id"
        dataSource={data}
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
      />

      <Modal title="新增记录" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
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
          <Form.Item name="note" label="备注"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/costs" />
    </div>
  );
}
