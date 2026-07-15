import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Form, Modal, Popconfirm, Select, Space, Table, Tag, message } from 'antd';
import {
  CheckCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  ImportOutlined,
  PlusOutlined,
  ReadOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type { TableRowSelection } from 'antd/es/table/interface';

import {
  createSystemTemplate,
  deleteSystemTemplate,
  importSystemCropTemplate,
  listSystemCropTemplates,
  updateSystemTemplate,
  type CropTemplate,
  type GrowthStage,
} from '../../api/crops';
import { PageShell, Toolbar } from '../../components/PageShell';
import TemplateForm from '../../components/TemplateForm';

const ALL_CATEGORIES = 'all';

type StageFormValue = {
  name?: string;
  duration_days?: number;
  key_tasks?: string;
};

function buildSavePayload(values: {
  name: string;
  variety?: string | null;
  category?: string | null;
  stages?: StageFormValue[];
}) {
  return {
    name: values.name,
    variety: values.variety ?? null,
    category: values.category ?? null,
    stages: (values.stages ?? []).map((stage, index) => ({
      name: stage.name ?? '',
      duration_days: stage.duration_days ?? 0,
      order_index: index,
      key_tasks: stage.key_tasks,
    })),
  };
}

function mapTemplateToFormValues(template: CropTemplate) {
  return {
    name: template.name,
    variety: template.variety,
    category: template.category,
    stages: (template.stages ?? []).map((stage: GrowthStage) => ({
      name: stage.name,
      duration_days: stage.duration_days,
      key_tasks: stage.key_tasks,
    })),
  };
}

export default function SystemLibrary() {
  const navigate = useNavigate();
  const [data, setData] = useState<CropTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [category, setCategory] = useState<string>(ALL_CATEGORIES);
  const [categoryOptions, setCategoryOptions] = useState<string[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const mergeCategoryOptions = useCallback((templates: CropTemplate[]) => {
    const values = templates
      .map((item) => item.category)
      .filter((value): value is string => Boolean(value));
    setCategoryOptions((current) => Array.from(new Set([...current, ...values])));
  }, []);

  const loadTemplates = useCallback(async (nextCategory: string) => {
    setLoading(true);
    try {
      const res = await listSystemCropTemplates(
        nextCategory === ALL_CATEGORIES ? undefined : nextCategory,
      );
      setData(res);
      mergeCategoryOptions(res);
      setSelectedRowKeys((keys) => keys.filter((key) => res.some((item) => item.id === key)));
    } catch {
      message.error('加载系统模板库失败');
    } finally {
      setLoading(false);
    }
  }, [mergeCategoryOptions]);

  useEffect(() => {
    loadTemplates(ALL_CATEGORIES);
  }, [loadTemplates]);

  const selectedTemplates = useMemo(
    () => data.filter((item) => selectedRowKeys.includes(item.id)),
    [data, selectedRowKeys],
  );

  const handleCategoryChange = (value: string) => {
    setCategory(value);
    setNotice(null);
    loadTemplates(value);
  };

  const handleImportSelected = async () => {
    if (selectedTemplates.length === 0) {
      message.warning('请先选择要导入的系统模板');
      return;
    }

    setImporting(true);
    try {
      const results = await Promise.all(
        selectedTemplates.map((template) => importSystemCropTemplate(template.id)),
      );
      const duplicateCount = results.filter((item) => item.already_exists).length;
      const createdCount = results.length - duplicateCount;

      if (duplicateCount > 0) {
        const text = '已存在相同模板，已为你跳过重复导入';
        setNotice(text);
        message.info(text);
      }
      if (createdCount > 0) {
        const text = `已导入 ${createdCount} 个系统模板`;
        setNotice(text);
        message.success(text);
      }
      setSelectedRowKeys([]);
    } catch {
      message.error('导入系统模板失败');
    } finally {
      setImporting(false);
    }
  };

  const openCreate = () => {
    setEditingId(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (record: CropTemplate) => {
    setEditingId(record.id);
    form.setFieldsValue(mapTemplateToFormValues(record));
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingId(null);
    form.resetFields();
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    const payload = buildSavePayload(values);
    setSaving(true);
    try {
      if (editingId === null) {
        await createSystemTemplate(payload);
        message.success('创建成功');
      } else {
        await updateSystemTemplate(editingId, payload);
        message.success('更新成功');
      }
      closeModal();
      loadTemplates(category);
    } catch {
      message.error(editingId === null ? '创建失败' : '更新失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteSystemTemplate(id);
      message.success('删除成功');
      loadTemplates(category);
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(typeof detail === 'string' && detail ? detail : '删除失败');
    }
  };

  const rowSelection: TableRowSelection<CropTemplate> = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 72 },
    {
      title: '名称',
      dataIndex: 'name',
      width: 150,
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 110,
      render: (text: string | null | undefined) => text ? <Tag color="green">{text}</Tag> : '-',
    },
    {
      title: '品种',
      dataIndex: 'variety',
      width: 140,
      render: (text: string | undefined) => text || '-',
    },
    {
      title: '生长阶段',
      key: 'stages',
      render: (_: unknown, record: CropTemplate) => (
        <Space wrap>
          <Tag color="blue">{record.stages?.length ?? 0} 个阶段</Tag>
          {record.stages?.slice(0, 4).map((stage) => (
            <Tag key={`${record.id}-${stage.order_index}-${stage.name}`}>{stage.name}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right' as const,
      render: (_: unknown, record: CropTemplate) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            description={`删除系统模版 "${record.name}"？已被农场导入的模版无法删除。`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageShell
      title="系统模板"
      description="管理平台预置的作物模板资产；导入后会生成当前管理员农场账号下的调试副本。"
      actions={<Button onClick={() => navigate('/crops')}>查看调试副本</Button>}
    >
      <Toolbar
        left={(
          <>
            <Select
              aria-label="作物分类"
              value={category}
              onChange={handleCategoryChange}
              style={{ width: 180 }}
              options={[
                { value: ALL_CATEGORIES, label: '全部分类' },
                ...categoryOptions.map((item) => ({ value: item, label: item })),
              ]}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={openCreate}
            >
              新建模版
            </Button>
            <Button
              icon={<ImportOutlined />}
              loading={importing}
              disabled={selectedRowKeys.length === 0}
              onClick={handleImportSelected}
            >
              导入所选
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => loadTemplates(category)} loading={loading}>
              刷新
            </Button>
          </>
        )}
        right={(
          <span style={{ color: '#8b949e', fontSize: 13 }}>
            <ReadOutlined /> 共 {data.length} 个系统模板
            {selectedRowKeys.length > 0 && (
              <span style={{ marginLeft: 8 }}>
                <CheckCircleOutlined /> 已选 {selectedRowKeys.length} 个
              </span>
            )}
          </span>
        )}
      />

      {notice && (
        <Alert
          showIcon
          type="info"
          message={notice}
          style={{ marginBottom: 12 }}
        />
      )}

      <Table
        rowKey="id"
        dataSource={data}
        columns={columns}
        loading={loading}
        rowSelection={rowSelection}
        size="small"
        scroll={{ x: 960 }}
        pagination={{
          pageSize: 20,
          showSizeChanger: true,
          pageSizeOptions: [10, 20, 50],
          showTotal: (count) => `共 ${count} 条`,
        }}
      />

      <Modal
        title={editingId !== null ? '编辑系统模版' : '新建系统模版'}
        open={modalOpen}
        onOk={handleSave}
        confirmLoading={saving}
        onCancel={closeModal}
        width={560}
        okText="确定"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <TemplateForm showCategory />
        </Form>
      </Modal>
    </PageShell>
  );
}
