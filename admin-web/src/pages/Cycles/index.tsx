import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message, Tag, Popconfirm } from 'antd';
import { PlusOutlined, BugOutlined, EyeOutlined, EditOutlined, DeleteOutlined, FieldTimeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { listCycles, createCycle, updateCycle, deleteCycle, type CropCycleListItem } from '../../api/cycles';
import { listTemplates, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';
import { PageShell, Toolbar } from '../../components/PageShell';

export default function Cycles() {
  const [data, setData] = useState<CropCycleListItem[]>([]);
  const [templates, setTemplates] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = async (page = pagination.current, pageSize = pagination.pageSize) => {
    setLoading(true);
    try {
      const [cyclesRes, tplRes] = await Promise.all([
        listCycles({ page, size: pageSize }),
        listTemplates(),
      ]);
      setData(cyclesRes.items);
      setPagination({ current: page, pageSize, total: cyclesRes.total });
      setTemplates(tplRes.items);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    try {
      await createCycle({ ...values, start_date: values.start_date.format('YYYY-MM-DD') });
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const openEdit = (record: CropCycleListItem) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      crop_template_id: templates.find((item) => item.name === record.crop_template_name)?.id,
      start_date: dayjs(record.start_date),
    });
    setModalOpen(true);
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
      fetchData();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteCycle(id);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '作物', dataIndex: 'crop_template_name', render: (text: string) => <Tag color="green">{text}</Tag> },
    { title: '开始日期', dataIndex: 'start_date' },
    { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'active' ? 'green' : 'default'}>{s === 'active' ? '进行中' : s}</Tag> },
    { title: '当前阶段', dataIndex: 'current_stage_name', render: (text: string | undefined) => text || '-' },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, r: CropCycleListItem) => (
        <Space>
          <Button icon={<EyeOutlined />} size="small" onClick={() => navigate(`/cycles/${r.id}`)}>详情</Button>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(r)}>编辑</Button>
          <Popconfirm
            title="确认删除"
            description={`删除 "${r.name}"？`}
            onConfirm={() => handleDelete(r.id)}
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
      title="种植周期"
      description="跟踪每个茬口从开始日期到当前阶段的进度，支持推进、编辑和日志联动。"
    >
      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新建茬口</Button>
            <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
          </>
        )}
        right={<span style={{ color: '#8b949e', fontSize: 13 }}><FieldTimeOutlined /> 共 {pagination.total} 个周期</span>}
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

      <Modal title={editingId !== null ? '编辑茬口' : '新建茬口'} open={modalOpen} onOk={editingId !== null ? handleUpdate : handleCreate} onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="crop_template_id" label="作物模板" rules={[{ required: true }]}>
            <Select options={templates.map((t) => ({ value: t.id, label: t.name }))} />
          </Form.Item>
          <Form.Item name="start_date" label="开始日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="field_name" label="地块名称"><Input /></Form.Item>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/cycles" />
    </PageShell>
  );
}
