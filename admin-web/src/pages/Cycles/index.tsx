import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, DatePicker, Select, Space, message, Tag, Popconfirm } from 'antd';
import { PlusOutlined, BugOutlined, EyeOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listCycles, createCycle, updateCycle, deleteCycle, type CropCycleListItem } from '../../api/cycles';
import { listTemplates, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';

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
      crop_template_id: record.crop_template_name,
      start_date: record.start_date,
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
    { title: '作物', dataIndex: 'crop_template_name' },
    { title: '开始日期', dataIndex: 'start_date' },
    { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'active' ? 'green' : 'default'}>{s}</Tag> },
    { title: '当前阶段', dataIndex: 'current_stage_name' },
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
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新建茬口</Button>
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
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
    </div>
  );
}
