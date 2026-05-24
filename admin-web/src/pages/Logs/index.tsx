import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message } from 'antd';
import { PlusOutlined, BugOutlined } from '@ant-design/icons';
import { listLogs, createLog, type FarmLog } from '../../api/logs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';

export default function Logs() {
  const [data, setData] = useState<FarmLog[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [filterCycleId, setFilterCycleId] = useState<number | undefined>();
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [logsRes, cyclesRes] = await Promise.all([
        listLogs(filterCycleId ? { cycle_id: filterCycleId } : undefined),
        listCycles(),
      ]);
      setData(logsRes.data);
      setCycles(cyclesRes.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [filterCycleId]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createLog({ ...values, operation_date: values.operation_date.format('YYYY-MM-DD') });
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
    { title: '茬口ID', dataIndex: 'cycle_id', width: 80 },
    { title: '操作类型', dataIndex: 'operation_type' },
    { title: '日期', dataIndex: 'operation_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
    { title: '创建时间', dataIndex: 'created_at' },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新增日志</Button>
        <Select placeholder="按茬口筛选" allowClear style={{ width: 200 }} value={filterCycleId}
          onChange={(v) => setFilterCycleId(v)} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title="新增日志" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="cycle_id" label="茬口" rules={[{ required: true }]}>
            <Select options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <Form.Item name="operation_type" label="操作类型" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="operation_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/logs" />
    </div>
  );
}
