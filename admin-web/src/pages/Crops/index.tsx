import { useCallback, useEffect, useState } from 'react';
import { Table, Button, Modal, Form, Input, InputNumber, Space, message, Divider, Popconfirm, Tag, Card, Alert } from 'antd';
import { PlusOutlined, MinusCircleOutlined, BugOutlined, EditOutlined, DeleteOutlined, ReadOutlined, RobotOutlined } from '@ant-design/icons';
import { listTemplates, createTemplate, updateTemplate, deleteTemplate, parseTemplate, type CropTemplate, type CropTemplateParseResponse } from '../../api/crops';
import ApiDebugger from '../../components/ApiDebugger';
import { PageShell, Toolbar } from '../../components/PageShell';
import { cardStyle } from '../../styles/theme';
import { buildTemplateFormValues } from '../Operations/smartCreateModel';

type StageFormValue = {
  name?: string;
  duration_days?: number;
  key_tasks?: string;
};

export default function Crops() {
  const [data, setData] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [debugOpen, setDebugOpen] = useState(false);
  const [smartText, setSmartText] = useState('');
  const [smartLoading, setSmartLoading] = useState(false);
  const [smartResult, setSmartResult] = useState<CropTemplateParseResponse | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = useCallback(async (page: number, pageSize: number) => {
    setLoading(true);
    try {
      const res = await listTemplates({ page, size: pageSize });
      setData(res.items);
      setPagination({ current: page, pageSize, total: res.total });
    } catch {
      message.error('加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(1, pagination.pageSize); }, [fetchData, pagination.pageSize]);

  const handleCreate = async () => {
    const values = await form.validateFields();
    const payload = {
      name: values.name,
      variety: values.variety,
      stages: (values.stages || []).map((s: StageFormValue, i: number) => ({
        ...s,
        order_index: i + 1,
      })),
    };
    try {
      await createTemplate(payload);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('创建失败');
    }
  };

  const openEdit = (record: CropTemplate) => {
    setSmartText('');
    setSmartResult(null);
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

  const openCreate = () => {
    setEditingId(null);
    setSmartText('');
    setSmartResult(null);
    form.resetFields();
    setModalOpen(true);
  };

  const handleSmartParse = async () => {
    if (!smartText.trim()) {
      message.warning('请输入作物模板描述');
      return;
    }
    setSmartLoading(true);
    try {
      const parsed = await parseTemplate(smartText.trim());
      setSmartResult(parsed);
      form.setFieldsValue(buildTemplateFormValues(parsed));
      message.success('已解析并回填模板');
    } catch {
      message.error('智能解析失败，请检查 AI 配置或改用手填');
    } finally {
      setSmartLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (editingId === null) return;
    const values = await form.validateFields();
    const payload = {
      name: values.name,
      variety: values.variety,
      stages: (values.stages || []).map((s: StageFormValue, i: number) => ({
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
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTemplate(id);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name', width: 150, render: (text: string) => <strong>{text}</strong> },
    { title: '品种', dataIndex: 'variety', width: 120, render: (text: string | undefined) => text || '-' },
    {
      title: '生长阶段',
      key: 'stages',
      render: (_: unknown, r: CropTemplate) => (
        <Space wrap>
          <Tag color="blue">{r.stages?.length ?? 0} 个阶段</Tag>
          {r.stages?.slice(0, 3).map((stage) => <Tag key={stage.order_index}>{stage.name}</Tag>)}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 210,
      fixed: 'right' as const,
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
    <PageShell
      title="作物模板"
      description="维护作物品种与生长阶段，为种植周期、日志和 AI 建议提供基础数据。"
    >
      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建模板</Button>
            <Button icon={<BugOutlined />} onClick={() => setDebugOpen(true)}>调试</Button>
          </>
        )}
        right={<span style={{ color: '#8b949e', fontSize: 13 }}><ReadOutlined /> 共 {pagination.total} 个模板</span>}
      />
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

      <Modal title={editingId !== null ? '编辑作物模板' : '新建作物模板'} open={modalOpen} onOk={editingId !== null ? handleUpdate : handleCreate} onCancel={() => { setModalOpen(false); setEditingId(null); form.resetFields(); }} width={560}>
        {editingId === null && (
          <Card size="small" title={<span><RobotOutlined /> 智能作物模板</span>} style={{ ...cardStyle, marginBottom: 16 }}>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={smartText}
                onChange={(event) => setSmartText(event.target.value)}
                onPressEnter={handleSmartParse}
                placeholder="例如：我要种 8424 西瓜，给我生成阶段"
              />
              <Button type="primary" loading={smartLoading} onClick={handleSmartParse}>解析回填</Button>
            </Space.Compact>
            {smartResult && (
              <Alert
                style={{ marginTop: 12 }}
                type="info"
                showIcon
                message="解析结果已填入下方表单，确认无误后再创建模板。"
                description={`${smartResult.name}${smartResult.variety ? ` · ${smartResult.variety}` : ''} · ${smartResult.stages.length} 个阶段`}
              />
            )}
          </Card>
        )}
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
    </PageShell>
  );
}
