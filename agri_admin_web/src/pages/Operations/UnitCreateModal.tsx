import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Row,
  Select,
  Space,
  Table,
  message,
} from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

import type { CropCycleListItem } from '../../api/cycles';
import { operationsApi, type PlantingUnit } from '../../api/operations';
import { buildRequestBody } from './workbenchModel';

type UnitCreateMode = 'single' | 'batch';
type NamingMode = 'number' | 'letter' | 'custom';

type UnitForm = {
  cycle_id: number;
  name: string;
  area_mu?: number | null;
  planted_date?: dayjs.Dayjs | null;
  status: string;
  note?: string;
};

type BatchUnitForm = {
  cycle_id: number;
  naming_mode: NamingMode;
  prefix?: string;
  suffix?: string;
  start_number?: number | null;
  start_letter?: string;
  count?: number | null;
  custom_names?: string;
  area_mu?: number | null;
  planted_date?: dayjs.Dayjs | null;
  status: string;
  note?: string;
};

type UnitDraft = {
  tempId: string;
  name: string;
  area_mu?: number | null;
  planted_date?: dayjs.Dayjs | null;
  status: string;
  note?: string;
};

type StatusOption = {
  value: string;
  label: string;
};

type UnitCreateModalProps = {
  open: boolean;
  cycles: CropCycleListItem[];
  selectedCycle?: number;
  existingUnits: PlantingUnit[];
  statusOptions: StatusOption[];
  onClose: () => void;
  onCreated: () => Promise<void>;
};

const maxBatchCount = 100;
const letterOptions = Array.from({ length: 26 }, (_, index) => {
  const letter = String.fromCharCode(65 + index);
  return { value: letter, label: letter };
});

export function UnitCreateModal({
  open,
  cycles,
  selectedCycle,
  existingUnits,
  statusOptions,
  onClose,
  onCreated,
}: UnitCreateModalProps) {
  const [mode, setMode] = useState<UnitCreateMode>('single');
  const [drafts, setDrafts] = useState<UnitDraft[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [singleForm] = Form.useForm<UnitForm>();
  const [batchForm] = Form.useForm<BatchUnitForm>();
  const namingMode = Form.useWatch('naming_mode', batchForm);
  const cycleOptions = useMemo(
    () => cycles.map((cycle) => ({ value: cycle.id, label: cycle.name })),
    [cycles],
  );
  const draftSummary = useMemo(() => {
    const totalArea = drafts.reduce((sum, draft) => sum + Number(draft.area_mu ?? 0), 0);
    return {
      count: drafts.length,
      totalArea: Number(totalArea.toFixed(2)),
    };
  }, [drafts]);

  useEffect(() => {
    if (!open) return;
    setMode('single');
    setDrafts([]);
    singleForm.resetFields();
    batchForm.resetFields();
    singleForm.setFieldsValue({ cycle_id: selectedCycle, status: 'active' });
    batchForm.setFieldsValue({
      cycle_id: selectedCycle,
      naming_mode: 'number',
      prefix: '',
      suffix: '号棚',
      start_number: 1,
      start_letter: 'A',
      count: 20,
      area_mu: 1,
      status: 'active',
    });
  }, [batchForm, open, selectedCycle, singleForm]);

  const closeModal = () => {
    if (submitting) return;
    onClose();
  };

  const updateDraft = (tempId: string, patch: Partial<UnitDraft>) => {
    setDrafts((current) => current.map((draft) => (
      draft.tempId === tempId ? { ...draft, ...patch } : draft
    )));
  };

  const removeDraft = (tempId: string) => {
    setDrafts((current) => current.filter((draft) => draft.tempId !== tempId));
  };

  const generateDrafts = async () => {
    const values = await batchForm.validateFields();
    const names = buildDraftNames(values);
    if (names.length === 0) {
      message.error('请先填写要创建的单元名称');
      return;
    }
    setDrafts(names.map((name, index) => ({
      tempId: `${Date.now()}-${index}`,
      name,
      area_mu: values.area_mu,
      planted_date: values.planted_date,
      status: values.status,
      note: values.note,
    })));
  };

  const createSingleUnit = async () => {
    const values = await singleForm.validateFields();
    const payload = buildRequestBody({
      ...values,
      planted_date: values.planted_date?.format('YYYY-MM-DD'),
    });
    await operationsApi.createUnit(payload as Omit<PlantingUnit, 'id' | 'farm_id' | 'created_at'>);
    message.success('种植单元已创建');
  };

  const createBatchUnits = async () => {
    const values = await batchForm.validateFields();
    const error = validateDrafts(drafts, existingUnits);
    if (error) {
      message.error(error);
      return false;
    }
    for (const draft of drafts) {
      const payload = buildRequestBody({
        cycle_id: values.cycle_id,
        name: draft.name.trim(),
        area_mu: draft.area_mu,
        planted_date: draft.planted_date?.format('YYYY-MM-DD'),
        status: draft.status,
        note: draft.note,
      });
      await operationsApi.createUnit(payload as Omit<PlantingUnit, 'id' | 'farm_id' | 'created_at'>);
    }
    message.success(`已创建 ${drafts.length} 个种植单元`);
    return true;
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      if (mode === 'single') {
        await createSingleUnit();
      } else {
        const created = await createBatchUnits();
        if (!created) return;
      }
      singleForm.resetFields();
      batchForm.resetFields();
      setDrafts([]);
      onClose();
      await onCreated();
    } finally {
      setSubmitting(false);
    }
  };

  const columns: ColumnsType<UnitDraft> = [
    {
      title: '单元名称',
      dataIndex: 'name',
      width: 180,
      render: (value: string, record) => (
        <Input
          aria-label={`单元名称 ${value}`}
          value={value}
          onChange={(event) => updateDraft(record.tempId, { name: event.target.value })}
        />
      ),
    },
    {
      title: '面积（亩）',
      dataIndex: 'area_mu',
      width: 140,
      render: (value: number | null | undefined, record) => (
        <InputNumber
          aria-label={`面积 ${record.name}`}
          min={0.01}
          precision={2}
          value={value}
          style={{ width: '100%' }}
          onChange={(nextValue) => updateDraft(record.tempId, { area_mu: nextValue })}
        />
      ),
    },
    {
      title: '种植日期',
      dataIndex: 'planted_date',
      width: 160,
      render: (value: dayjs.Dayjs | null | undefined, record) => (
        <DatePicker
          aria-label={`种植日期 ${record.name}`}
          value={value}
          style={{ width: '100%' }}
          onChange={(nextValue) => updateDraft(record.tempId, { planted_date: nextValue })}
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 120,
      render: (value: string, record) => (
        <Select
          aria-label={`状态 ${record.name}`}
          value={value}
          options={statusOptions}
          style={{ width: '100%' }}
          onChange={(nextValue) => updateDraft(record.tempId, { status: nextValue })}
        />
      ),
    },
    {
      title: '备注',
      dataIndex: 'note',
      render: (value: string | undefined, record) => (
        <Input
          aria-label={`备注 ${record.name}`}
          value={value}
          onChange={(event) => updateDraft(record.tempId, { note: event.target.value })}
        />
      ),
    },
    {
      title: '操作',
      width: 80,
      render: (_, record) => (
        <Button danger size="small" icon={<DeleteOutlined />} onClick={() => removeDraft(record.tempId)}>
          删除
        </Button>
      ),
    },
  ];

  return (
    <Modal
      title="新建种植单元"
      open={open}
      onOk={submit}
      onCancel={closeModal}
      width={mode === 'batch' ? 960 : 560}
      okText={mode === 'batch' && drafts.length > 0 ? `创建 ${drafts.length} 个种植单元` : '创建种植单元'}
      okButtonProps={{ disabled: mode === 'batch' && drafts.length === 0, loading: submitting }}
      cancelButtonProps={{ disabled: submitting }}
      destroyOnHidden
    >
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Button.Group>
          <Button type={mode === 'single' ? 'primary' : 'default'} onClick={() => setMode('single')}>
            单个创建
          </Button>
          <Button type={mode === 'batch' ? 'primary' : 'default'} onClick={() => setMode('batch')}>
            批量创建
          </Button>
        </Button.Group>

        {mode === 'single' ? (
          <Form form={singleForm} layout="vertical">
            <Form.Item name="cycle_id" label="茬口" rules={[{ required: true, message: '请选择茬口' }]}>
              <Select options={cycleOptions} />
            </Form.Item>
            <Form.Item name="name" label="单元名称" rules={[{ required: true, message: '请输入单元名称' }]}>
              <Input placeholder="东棚 A 区" />
            </Form.Item>
            <Row gutter={12}>
              <Col span={12}>
                <Form.Item name="area_mu" label="面积（亩）">
                  <InputNumber min={0} precision={2} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="planted_date" label="种植日期">
                  <DatePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
            <Form.Item name="status" label="状态" initialValue="active">
              <Select options={statusOptions} />
            </Form.Item>
            <Form.Item name="note" label="备注">
              <Input.TextArea rows={3} />
            </Form.Item>
          </Form>
        ) : (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Form form={batchForm} layout="vertical">
              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="cycle_id" label="茬口" rules={[{ required: true, message: '请选择茬口' }]}>
                    <Select options={cycleOptions} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="naming_mode" label="命名方式" initialValue="number">
                    <Select
                      options={[
                        { value: 'number', label: '数字序列' },
                        { value: 'letter', label: '字母序列' },
                        { value: 'custom', label: '自定义清单' },
                      ]}
                      onChange={() => setDrafts([])}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="area_mu" label="默认面积（亩）" rules={[{ required: true, message: '请输入默认面积' }]}>
                    <InputNumber min={0.01} precision={2} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              {namingMode === 'custom' ? (
                <Form.Item name="custom_names" label="单元名称清单" rules={[{ required: true, message: '请输入单元名称' }]}>
                  <Input.TextArea rows={4} placeholder={'东棚A区\n东棚B区\n西棚1号'} />
                </Form.Item>
              ) : (
                <Row gutter={12}>
                  <Col span={6}>
                    <Form.Item name="prefix" label="名称前缀">
                      <Input placeholder="东棚" />
                    </Form.Item>
                  </Col>
                  {namingMode === 'letter' ? (
                    <Col span={6}>
                      <Form.Item name="start_letter" label="起始字母">
                        <Select options={letterOptions} />
                      </Form.Item>
                    </Col>
                  ) : (
                    <Col span={6}>
                      <Form.Item name="start_number" label="起始序号">
                        <InputNumber min={1} precision={0} style={{ width: '100%' }} />
                      </Form.Item>
                    </Col>
                  )}
                  <Col span={6}>
                    <Form.Item name="count" label="数量" rules={[{ required: true, message: '请输入数量' }]}>
                      <InputNumber min={1} max={maxBatchCount} precision={0} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item name="suffix" label="名称后缀">
                      <Input placeholder="号棚" />
                    </Form.Item>
                  </Col>
                </Row>
              )}

              <Row gutter={12}>
                <Col span={8}>
                  <Form.Item name="planted_date" label="种植日期">
                    <DatePicker style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="status" label="状态" initialValue="active">
                    <Select options={statusOptions} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="note" label="默认备注">
                    <Input />
                  </Form.Item>
                </Col>
              </Row>
              <Button type="primary" onClick={generateDrafts}>
                生成草稿
              </Button>
            </Form>

            {drafts.length > 0 && (
              <>
                <Alert
                  type="info"
                  showIcon
                  message={`已生成 ${draftSummary.count} 个草稿，合计 ${draftSummary.totalArea} 亩`}
                />
                <Table
                  rowKey="tempId"
                  size="small"
                  dataSource={drafts}
                  columns={columns}
                  pagination={false}
                  scroll={{ x: 880, y: 360 }}
                />
              </>
            )}
          </Space>
        )}
      </Space>
    </Modal>
  );
}

function buildDraftNames(values: BatchUnitForm): string[] {
  if (values.naming_mode === 'custom') {
    return (values.custom_names ?? '')
      .split(/[\n,，、]+/)
      .map((item) => item.trim())
      .filter(Boolean)
      .slice(0, maxBatchCount);
  }
  const count = Math.min(Number(values.count ?? 0), maxBatchCount);
  const prefix = values.prefix ?? '';
  const suffix = values.suffix ?? '';
  if (values.naming_mode === 'letter') {
    const startCode = (values.start_letter ?? 'A').toUpperCase().charCodeAt(0);
    return Array.from({ length: count }, (_, index) => `${prefix}${String.fromCharCode(startCode + index)}${suffix}`);
  }
  const start = Number(values.start_number ?? 1);
  return Array.from({ length: count }, (_, index) => `${prefix}${start + index}${suffix}`);
}

function validateDrafts(drafts: UnitDraft[], existingUnits: PlantingUnit[]): string | null {
  if (drafts.length === 0) return '请先生成草稿';
  const existingNames = new Set(existingUnits.map((unit) => unit.name.trim()));
  const draftNames = new Set<string>();
  for (const draft of drafts) {
    const name = draft.name.trim();
    if (!name) return '草稿中存在空名称，请补充后再创建';
    if (draftNames.has(name)) return `草稿中存在重复名称：${name}`;
    if (existingNames.has(name)) return `当前茬口已存在：${name}`;
    if (draft.area_mu !== null && draft.area_mu !== undefined && Number(draft.area_mu) <= 0) {
      return `${name} 的面积必须大于 0`;
    }
    draftNames.add(name);
  }
  return null;
}
