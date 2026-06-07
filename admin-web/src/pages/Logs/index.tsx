import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message, Popconfirm } from 'antd';
import { PlusOutlined, BugOutlined, EditOutlined, DeleteOutlined, FormOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { listLogs, createLog, updateLog, deleteLog, type FarmLog } from '../../api/logs';
import { listCycles, type CropCycleListItem } from '../../api/cycles';
import ApiDebugger from '../../components/ApiDebugger';
import { PageShell, Toolbar } from '../../components/PageShell';

export default function Logs() {
  const [data, setData] = useState<FarmLog[]>([]);
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [filterCycleId, setFilterCycleId] = useState<number | undefined>();
  const [form] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = async (page = pagination.current, pageSize = pagination.pageSize) => {
    setLoading(true);
    try {
      const [logsRes, cyclesRes] = await Promise.all([
        listLogs(filterCycleId ? { cycle_id: filterCycleId, page, size: pageSize } : { page, size: pageSize }),
        listCycles(),
      ]);
      setData(logsRes.items);
      setPagination({ current: page, pageSize, total: logsRes.total });
      setCycles(cyclesRes.items);
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

  const openEdit = (record: FarmLog) => {
    setEditingId(record.id);
    form.setFieldsValue({
      cycle_id: record.cycle_id,
      operation_type: record.operation_type,
      operation_date: dayjs(record.operation_date),
      note: record.note,
    });
    setModalOpen(true);
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const values = await form.validateFields();
    try {
      await updateLog(editingId, { ...values, operation_date: values.operation_date.format('YYYY-MM-DD') });
      message.success('更新成功');
      setModalOpen(false);
      setEditingId(null);
      form.resetFields();
      fetchData();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteLog(id);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '茬口ID', dataIndex: 'cycle_id', width: 80 },
    { title: '操作类型', dataIndex: 'operation_type', render: (text: string) => <strong>{text}</strong> },
    { title: '日期', dataIndex: 'operation_date' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
    { title: '创建时间', dataIndex: 'created_at' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: FarmLog) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm
            title="确认删除"
            description={`删除日志 #${record.id}？`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button danger icon={<DeleteOutlined />} size="small">删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="农事日志"
      description="记录浇水、施肥、巡检等操作，帮助后续报告和 AI 建议追溯上下文。"
    >
      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新增日志</Button>
            <Select placeholder="按茬口筛选" allowClear style={{ width: 220 }} value={filterCycleId}
              onChange={(v) => setFilterCycleId(v)} options={cycles.map((c) => ({ value: c.id, label: c.name }))} />
            <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
          </>
        )}
        right={<span style={{ color: '#8b949e', fontSize: 13 }}><FormOutlined /> 共 {pagination.total} 条日志</span>}
      />
      <Table
        rowKey="id"
        dataSource={data}
        columns={columns}
        loading={loading}
        size="middle"
        scroll={{ x: 860 }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
          showTotal: (count) => `共 ${count} 条`,
        }}
        onChange={(p) => fetchData(p.current, p.pageSize)}
      />

      <Modal title={editingId !== null ? '编辑日志' : '新增日志'} open={modalOpen} onOk={editingId !== null ? handleUpdate : handleCreate} onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }}>
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
    </PageShell>
  );
}
