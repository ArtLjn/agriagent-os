import { useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, Space, message, Divider, Popconfirm } from 'antd';
import { PlusOutlined, MinusCircleOutlined, BugOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { listTemplates, createTemplate, updateTemplate, deleteTemplate, type CropTemplate } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';

export default function Crops() {
  const [data, setData] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await listTemplates();
      setData(res.data);
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleCreate = async () => {
    const values = await form.validateFields();
    const payload = {
      name: values.name,
      variety: values.variety,
      stages: (values.stages || []).map((s: any, i: number) => ({
        ...s,
        order_index: i + 1,
      })),
    };
    try {
      await createTemplate(payload);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch {
      message.error('创建失败');
    }
  };

  const openEdit = (record: CropTemplate) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      variety: record.variety,
      stages: record.stages.map((s) => ({
        name: s.name,
        duration_days: s.duration_days,
        key_tasks: s.key_tasks,
      })),
    });
    setModalOpen(true);
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const values = await form.validateFields();
    const payload = {
      name: values.name,
      variety: values.variety,
      stages: (values.stages || []).map((s: any, i: number) => ({
        ...s,
        order_index: i + 1,
      })),
    };
    try {
      await updateTemplate(editingId, payload);
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
      await deleteTemplate(id);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '品种', dataIndex: 'variety' },
    { title: '阶段数', key: 'stages', render: (_: unknown, r: CropTemplate) => r.stages?.length ?? 0 },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: CropTemplate) => (
        <Space>
          <Button icon={<EditOutlined />} size="small" onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm
            title="确认删除"
            description={`删除 "${record.name}"？`}
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
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingId(null); form.resetFields(); setModalOpen(true); }}>新建模板</Button>
        <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
      </Space>
      <Table rowKey="id" dataSource={data} columns={columns} loading={loading} />

      <Modal title={editingId !== null ? '编辑作物模板' : '新建作物模板'} open={modalOpen} onOk={editingId !== null ? handleUpdate : handleCreate} onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }} width={560}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入模板名称' }]}><Input placeholder="如：西瓜" /></Form.Item>
          <Form.Item name="variety" label="品种"><Input placeholder="如：8424" /></Form.Item>

          <Divider>生长阶段</Divider>
          <Form.List name="stages">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item {...restField} name={[name, 'name']} rules={[{ required: true, message: '阶段名' }]}>
                      <Input placeholder="阶段名" style={{ width: 120 }} />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'duration_days']} rules={[{ required: true, message: '天数' }]}>
                      <InputNumber placeholder="天数" min={1} style={{ width: 90 }} />
                    </Form.Item>
                    <Form.Item {...restField} name={[name, 'key_tasks']}>
                      <Input placeholder="关键任务（选填）" style={{ width: 160 }} />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} />
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>添加阶段</Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>

      <ApiDebugger open={debugOpen} onClose={() => setDebugOpen(false)} defaultMethod="GET" defaultUrl="/crops/templates" />
    </div>
  );
}
