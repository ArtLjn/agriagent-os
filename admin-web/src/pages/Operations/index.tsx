import { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  AppstoreOutlined,
  CheckCircleOutlined,
  CloudDownloadOutlined,
  DeleteOutlined,
  DollarOutlined,
  FieldTimeOutlined,
  FormOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { PageShell, Toolbar, MetricCard } from '../../components/PageShell';
import { cardStyle, palette } from '../../styles/theme';
import { createCycle, listCycles, type CropCycleListItem, type CycleParseResponse } from '../../api/cycles';
import { createTemplate, type CropTemplateParseResponse } from '../../api/crops';
import { createRecord, type CostParseResponse } from '../../api/costs';
import { listAppSkills, type AppSkillItem, type AppSkillListResponse } from '../../api/agent';
import {
  operationsApi,
  type CostCategory,
  type DebtListResponse,
  type OperationWorkOrder,
  type PlantingUnit,
  type RecentOperation,
  type UserSettings,
  type VersionCheck,
  type Worker,
  type WorkerLaborSummary,
} from '../../api/operations';
import { parseSmartFill } from '../../api/smartFill';
import {
  buildRequestBody,
  calculateLaborAmount,
  createClientRequestId,
  formatMoney,
  normalizeOperationOptions,
} from './workbenchModel';
import { buildCostCreatePayload, buildCostFormValues } from '../Costs/costSmartFill';
import {
  SMART_FILL_FALLBACK_SCENARIOS,
  buildCycleFormValues,
  buildTemplateFormValues,
  inferSmartFillScene,
  isSupportedSmartCreateScene,
  normalizeSmartResult,
  type SmartCreateMeta,
  type SmartCreateResult,
} from './smartCreateModel';

type UnitForm = {
  cycle_id: number;
  name: string;
  area_mu?: number | null;
  planted_date?: dayjs.Dayjs | null;
  status: string;
  note?: string;
};

type WorkerForm = {
  name: string;
  phone?: string;
  default_pay_type: string;
  default_unit_price?: number | null;
  status: string;
  note?: string;
};

type WorkOrderForm = {
  cycle_id?: number;
  operation_type: string;
  operation_date: dayjs.Dayjs;
  scope_type: string;
  unit_ids?: number[];
  worker_id?: number;
  quantity?: number;
  unit_price?: number;
  paid_amount?: number;
  note?: string;
};

type WageForm = {
  cycle_id: number;
  operation_type: string;
  work_date: dayjs.Dayjs;
  worker_id?: number;
  worker_name?: string;
  crop_name?: string;
  pay_type: string;
  quantity: number;
  unit_price: number;
  paid_amount: number;
  note?: string;
};

type DebtForm = {
  counterparty: string;
  amount: number;
  category: string;
  record_date: dayjs.Dayjs;
  due_date?: dayjs.Dayjs;
  note?: string;
};

type CategoryForm = {
  name: string;
  type: 'cost' | 'income';
  icon: string;
  sort_order: number;
};

type SettingsForm = {
  display_name: string;
  default_city?: string;
  default_lat?: number | null;
  default_lon?: number | null;
  assistant_role?: 'professional' | 'warm' | 'creative';
};

const assistantRoleOptions = [
  {
    value: 'professional',
    label: '冷静专业型',
    description: '结论优先、克制准确，适合业务问答和技术支持。',
  },
  {
    value: 'warm',
    label: '温暖陪伴型',
    description: '自然亲切、耐心稳定，默认回答风格。',
  },
  {
    value: 'creative',
    label: '灵感创意型',
    description: '表达鲜活、主动发散，适合创意和方案讨论。',
  },
] as const;

const payTypeOptions = [
  { value: 'daily', label: '按天' },
  { value: 'piece', label: '计件' },
  { value: 'hourly', label: '按小时' },
];

const statusOptions = [
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' },
];

const defaultCategoryIcons = [
  { value: 'seed', label: '种苗' },
  { value: 'fertilizer', label: '肥料' },
  { value: 'labor', label: '人工' },
  { value: 'tool', label: '农具' },
  { value: 'income', label: '收入' },
  { value: 'other', label: '其他' },
];

const previewPanelStyle = {
  minHeight: 286,
  padding: 16,
  background: palette.bgPanel,
  border: `1px solid ${palette.border}`,
  borderRadius: 8,
};

const rawPreviewStyle = {
  margin: 0,
  maxHeight: 220,
  overflow: 'auto',
  color: palette.text,
  background: palette.bg,
  border: `1px solid ${palette.border}`,
  borderRadius: 8,
  padding: 12,
};

function statusTag(status: string) {
  const active = status === 'active';
  return <Tag color={active ? 'success' : 'default'}>{active ? '启用' : status}</Tag>;
}

function useCycles() {
  const [cycles, setCycles] = useState<CropCycleListItem[]>([]);

  const refreshCycles = useCallback(async () => {
    const res = await listCycles({ page: 1, size: 100 });
    setCycles(res.items);
  }, []);

  useEffect(() => {
    refreshCycles().catch(() => undefined);
  }, [refreshCycles]);

  return { cycles, refreshCycles };
}

export default function Operations() {
  const { cycles } = useCycles();

  return (
    <PageShell
      title="业务调试中心"
      description="把移动端和业务 API 的关键能力集中在一个管理端页面中，便于创建数据、联动调试和排查上下文。"
    >
      <Tabs
        items={[
          {
            key: 'smart',
            label: <span><RobotOutlined /> 智能创建</span>,
            children: <SmartCreatePanel />,
          },
          {
            key: 'planting',
            label: <span><FieldTimeOutlined /> 种植与作业</span>,
            children: <PlantingPanel cycles={cycles} />,
          },
          {
            key: 'labor',
            label: <span><TeamOutlined /> 工人用工</span>,
            children: <LaborPanel cycles={cycles} />,
          },
          {
            key: 'finance',
            label: <span><DollarOutlined /> 赊账与分类</span>,
            children: <FinancePanel />,
          },
          {
            key: 'settings',
            label: <span><SettingOutlined /> 用户与应用</span>,
            children: <SystemPanel />,
          },
        ]}
      />
    </PageShell>
  );
}

function SmartCreatePanel() {
  const [smartText, setSmartText] = useState('');
  const [smartResult, setSmartResult] = useState<SmartCreateResult | null>(null);
  const [smartMeta, setSmartMeta] = useState<SmartCreateMeta | null>(null);
  const [smartLoading, setSmartLoading] = useState(false);
  const [creatingScene, setCreatingScene] = useState<string | null>(null);

  const getScenario = useCallback(
    (key: string) => SMART_FILL_FALLBACK_SCENARIOS.find((item) => item.key === key),
    [],
  );

  const runSmartParse = async () => {
    if (!smartText.trim()) {
      message.warning('请输入要测试的业务描述');
      return;
    }
    const inferredScene = inferSmartFillScene(smartText);
    if (inferredScene === 'unsupported') {
      setSmartResult({
        scene: 'unsupported',
        sourceScene: 'unsupported',
        draft: { text: smartText.trim() },
      });
      setSmartMeta({
        missingFields: ['scene'],
        warnings: ['暂未识别出可智能填写的业务类型，请补充作物模板、茬口、记账或工人档案信息。'],
      });
      return;
    }
    const inferredScenario = getScenario(inferredScene);
    setSmartLoading(true);
    try {
      const response = await parseSmartFill<unknown>(inferredScene, smartText.trim());
      setSmartResult(normalizeSmartResult(response.scene, response.draft));
      setSmartMeta({
        missingFields: response.missing_fields,
        warnings: response.warnings,
      });
      message.success(`${getScenario(response.scene)?.title || inferredScenario?.title || '智能填写'}解析完成`);
    } catch {
      message.error(`${inferredScenario?.title || '智能填写'}解析失败`);
    } finally {
      setSmartLoading(false);
    }
  };

  const createParsedTemplate = async (draft: CropTemplateParseResponse) => {
    setCreatingScene('crop.template');
    try {
      const values = buildTemplateFormValues(draft);
      await createTemplate({
        ...values,
        stages: values.stages.map((stage, index) => ({ ...stage, order_index: index + 1 })),
      });
      setSmartResult(null);
      setSmartMeta(null);
      message.success('作物模板已创建');
    } catch {
      message.error('作物模板创建失败，请检查解析结果或后端服务');
    } finally {
      setCreatingScene(null);
    }
  };

  const createParsedCycle = async (draft: CycleParseResponse) => {
    if (!draft.crop_template_id) {
      message.warning('解析结果没有匹配到作物模板，请先到作物模板页创建或手动选择');
      return;
    }
    setCreatingScene('crop.cycle');
    try {
      const values = buildCycleFormValues(draft);
      await createCycle({
        name: values.name,
        crop_template_id: draft.crop_template_id,
        start_date: values.start_date.format('YYYY-MM-DD'),
        field_name: values.field_name,
      });
      setSmartResult(null);
      setSmartMeta(null);
      message.success('茬口已创建');
    } catch {
      message.error('茬口创建失败，请检查解析结果或后端服务');
    } finally {
      setCreatingScene(null);
    }
  };

  const createParsedCost = async (draft: CostParseResponse) => {
    setCreatingScene('ledger.record');
    try {
      const values = buildCostFormValues(draft);
      await createRecord(buildCostCreatePayload(values));
      setSmartResult(null);
      setSmartMeta(null);
      message.success('记账记录已创建');
    } catch {
      message.error('记账记录创建失败，请检查茬口、分类或后端服务');
    } finally {
      setCreatingScene(null);
    }
  };

  const createParsedWorker = async (draft: Omit<Worker, 'id' | 'farm_id' | 'created_at'>) => {
    setCreatingScene('labor.worker');
    try {
      await operationsApi.createWorker(buildRequestBody(draft) as Omit<Worker, 'id' | 'farm_id' | 'created_at'>);
      setSmartResult(null);
      setSmartMeta(null);
      message.success('工人档案已创建');
    } catch {
      message.error('工人档案创建失败，请检查解析结果或后端服务');
    } finally {
      setCreatingScene(null);
    }
  };

  return (
    <Card
      title={<Space size={8}><RobotOutlined /><span>智能填写</span></Space>}
      style={cardStyle}
    >
      <Row gutter={[20, 20]} align="top">
        <Col xs={24} xl={12}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Input.TextArea
              rows={8}
              value={smartText}
              onChange={(event) => {
                setSmartText(event.target.value);
                setSmartResult(null);
                setSmartMeta(null);
              }}
              placeholder="例如：我要种 8424 西瓜，生成完整生长阶段；4 月 1 日在东棚种一茬西瓜；今天买肥料 128 元"
            />
            <Button type="primary" block loading={smartLoading} onClick={runSmartParse}>
              按语义解析智能填写
            </Button>
            <Typography.Text type="secondary">
              系统会根据语义自动判断作物模板、茬口、记账或工人档案，不需要先选择智能填写列表。
            </Typography.Text>
          </Space>
        </Col>
        <Col xs={24} xl={12}>
          <div style={previewPanelStyle}>
            {smartMeta && (smartMeta.missingFields.length > 0 || smartMeta.warnings.length > 0) && (
              <Alert
                type={smartMeta.missingFields.length > 0 ? 'warning' : 'info'}
                showIcon
                style={{ marginBottom: 12 }}
                message={[
                  ...smartMeta.missingFields.map((field) => `缺少 ${field}`),
                  ...smartMeta.warnings,
                ].join('；')}
              />
            )}
            {!smartResult && <Empty description="暂无解析结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
            {smartResult?.scene === 'crop.template' && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Typography.Text strong>
                  {smartResult.draft.name}{smartResult.draft.variety ? ` · ${smartResult.draft.variety}` : ''}
                </Typography.Text>
                <Space wrap>
                  {smartResult.draft.stages.map((stage) => (
                    <Tag key={stage.order_index}>{stage.name} · {stage.duration_days}天</Tag>
                  ))}
                </Space>
                <Button loading={creatingScene === 'crop.template'} onClick={() => createParsedTemplate(smartResult.draft)}>
                  确认创建模板
                </Button>
              </Space>
            )}
            {smartResult?.scene === 'crop.cycle' && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="名称">{smartResult.draft.name}</Descriptions.Item>
                  <Descriptions.Item label="模板 ID">{smartResult.draft.crop_template_id ?? '未匹配'}</Descriptions.Item>
                  <Descriptions.Item label="开始日期">{smartResult.draft.start_date}</Descriptions.Item>
                  <Descriptions.Item label="地块">{smartResult.draft.field_name || '-'}</Descriptions.Item>
                </Descriptions>
                <Button loading={creatingScene === 'crop.cycle'} onClick={() => createParsedCycle(smartResult.draft)}>
                  确认创建茬口
                </Button>
              </Space>
            )}
            {smartResult?.scene === 'ledger.record' && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="类型">{smartResult.draft.record_type === 'income' ? '收入' : '支出'}</Descriptions.Item>
                  <Descriptions.Item label="分类">{smartResult.draft.category}</Descriptions.Item>
                  <Descriptions.Item label="金额">{formatMoney(smartResult.draft.amount)}</Descriptions.Item>
                  <Descriptions.Item label="日期">{smartResult.draft.record_date}</Descriptions.Item>
                  <Descriptions.Item label="赊账">{smartResult.draft.record_subtype === '赊账' ? '是' : '否'}</Descriptions.Item>
                  <Descriptions.Item label="对象">{smartResult.draft.counterparty || '-'}</Descriptions.Item>
                  <Descriptions.Item label="到期日">{smartResult.draft.due_date || '-'}</Descriptions.Item>
                  <Descriptions.Item label="备注">{smartResult.draft.note || '-'}</Descriptions.Item>
                </Descriptions>
                <Button loading={creatingScene === 'ledger.record'} onClick={() => createParsedCost(smartResult.draft)}>
                  确认创建记账
                </Button>
              </Space>
            )}
            {smartResult?.scene === 'labor.worker' && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="姓名">{smartResult.draft.name}</Descriptions.Item>
                  <Descriptions.Item label="电话">{smartResult.draft.phone || '-'}</Descriptions.Item>
                  <Descriptions.Item label="默认计薪">{payTypeOptions.find((item) => item.value === smartResult.draft.default_pay_type)?.label || smartResult.draft.default_pay_type}</Descriptions.Item>
                  <Descriptions.Item label="默认单价">{smartResult.draft.default_unit_price ? formatMoney(smartResult.draft.default_unit_price) : '-'}</Descriptions.Item>
                  <Descriptions.Item label="状态">{smartResult.draft.status === 'active' ? '启用' : '停用'}</Descriptions.Item>
                  <Descriptions.Item label="备注">{smartResult.draft.note || '-'}</Descriptions.Item>
                </Descriptions>
                <Button
                  disabled={(smartMeta?.missingFields.length ?? 0) > 0}
                  loading={creatingScene === 'labor.worker'}
                  onClick={() => createParsedWorker(smartResult.draft)}
                >
                  确认创建工人
                </Button>
              </Space>
            )}
            {smartResult?.scene === 'unsupported' && (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Typography.Text strong>{smartResult.sourceScene}</Typography.Text>
                <pre style={rawPreviewStyle}>{JSON.stringify(smartResult.draft, null, 2)}</pre>
              </Space>
            )}
            {smartResult && smartResult.scene !== 'unsupported' && isSupportedSmartCreateScene(smartResult.scene) && (
              <Typography.Text type="secondary">
                已识别为：{getScenario(smartResult.scene)?.title || smartResult.scene}
              </Typography.Text>
            )}
          </div>
        </Col>
      </Row>
    </Card>
  );
}

function PlantingPanel({ cycles }: { cycles: CropCycleListItem[] }) {
  const [units, setUnits] = useState<PlantingUnit[]>([]);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [workOrders, setWorkOrders] = useState<OperationWorkOrder[]>([]);
  const [recent, setRecent] = useState<RecentOperation[]>([]);
  const [operationOptions, setOperationOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | undefined>();
  const [loading, setLoading] = useState(false);
  const [unitOpen, setUnitOpen] = useState(false);
  const [orderOpen, setOrderOpen] = useState(false);
  const [unitForm] = Form.useForm<UnitForm>();
  const [orderForm] = Form.useForm<WorkOrderForm>();
  const [orderTotal, setOrderTotal] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [unitsRes, workersRes, ordersRes, recentRes, typesRes] = await Promise.all([
        operationsApi.listUnits(selectedCycle),
        operationsApi.listWorkers(true),
        operationsApi.listWorkOrders({ cycle_id: selectedCycle, page: 1, size: 20 }),
        operationsApi.listRecentOperations({ cycle_id: selectedCycle, days: 60, limit: 20 }),
        operationsApi.listOperationTypes(),
      ]);
      setUnits(unitsRes.data);
      setWorkers(workersRes.data);
      setWorkOrders(ordersRes.data.items);
      setOrderTotal(ordersRes.data.total);
      setRecent(recentRes.data);
      setOperationOptions(normalizeOperationOptions(typesRes.data));
    } catch {
      message.error('加载种植作业数据失败');
    } finally {
      setLoading(false);
    }
  }, [selectedCycle]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createUnit = async () => {
    const values = await unitForm.validateFields();
    const payload = buildRequestBody({
      ...values,
      planted_date: values.planted_date?.format('YYYY-MM-DD'),
    });
    await operationsApi.createUnit(payload as Omit<PlantingUnit, 'id' | 'farm_id' | 'created_at'>);
    message.success('种植单元已创建');
    setUnitOpen(false);
    unitForm.resetFields();
    await refresh();
  };

  const createWorkOrder = async () => {
    const values = await orderForm.validateFields();
    const laborAmount = calculateLaborAmount(values.quantity, values.unit_price, values.paid_amount);
    const laborEntries = values.worker_id
      ? [{
        worker_id: values.worker_id,
        pay_type: 'daily',
        quantity: values.quantity ?? 1,
        unit_price: values.unit_price ?? 0,
        paid_amount: values.paid_amount ?? 0,
        note: `管理端录入，应付 ${laborAmount.payable}，未付 ${laborAmount.unpaid}`,
      }]
      : [];
    await operationsApi.createWorkOrder({
      cycle_id: values.cycle_id,
      operation_type: values.operation_type,
      operation_date: values.operation_date.format('YYYY-MM-DD'),
      scope_type: values.scope_type,
      unit_ids: values.unit_ids ?? [],
      note: values.note,
      labor_entries: laborEntries,
    });
    message.success('作业单已创建');
    setOrderOpen(false);
    orderForm.resetFields();
    await refresh();
  };

  const unitColumns: ColumnsType<PlantingUnit> = [
    { title: 'ID', dataIndex: 'id', width: 64 },
    { title: '单元', dataIndex: 'name', render: (text: string) => <strong>{text}</strong> },
    { title: '茬口', dataIndex: 'cycle_id', width: 90 },
    { title: '面积', dataIndex: 'area_mu', render: (value) => value ? `${value} 亩` : '-' },
    { title: '种植日期', dataIndex: 'planted_date', render: (value) => value || '-' },
    { title: '状态', dataIndex: 'status', render: statusTag },
    {
      title: '操作',
      width: 100,
      render: (_, record) => (
        <Popconfirm title="确认删除" description={`删除 ${record.name}？`} onConfirm={async () => {
          await operationsApi.deleteUnit(record.id);
          message.success('种植单元已删除');
          await refresh();
        }}>
          <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  const orderColumns: ColumnsType<OperationWorkOrder> = [
    { title: 'ID', dataIndex: 'id', width: 64 },
    { title: '作业', dataIndex: 'operation_type', render: (text: string) => <Tag color="blue">{text}</Tag> },
    { title: '日期', dataIndex: 'operation_date', width: 120 },
    { title: '范围', dataIndex: 'scope_type', width: 90 },
    { title: '单元', dataIndex: 'unit_names', render: (names: string[]) => names?.length ? names.join('、') : '-' },
    { title: '应付人工', dataIndex: 'total_payable_amount', render: formatMoney },
    { title: '未付人工', dataIndex: 'total_unpaid_amount', render: (value) => <span style={{ color: Number(value) > 0 ? palette.warning : palette.textMuted }}>{formatMoney(value)}</span> },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Toolbar
        left={(
          <>
            <Select
              placeholder="按茬口筛选"
              allowClear
              style={{ width: 240 }}
              value={selectedCycle}
              onChange={setSelectedCycle}
              options={cycles.map((cycle) => ({ value: cycle.id, label: cycle.name }))}
            />
            <Button type="primary" icon={<PlusOutlined />} onClick={() => {
              unitForm.setFieldsValue({ cycle_id: selectedCycle, status: 'active' });
              setUnitOpen(true);
            }}>新建种植单元</Button>
            <Button icon={<FormOutlined />} onClick={() => {
              orderForm.setFieldsValue({ cycle_id: selectedCycle, operation_date: dayjs(), scope_type: 'cycle', quantity: 1, paid_amount: 0 });
              setOrderOpen(true);
            }}>新建作业单</Button>
          </>
        )}
        right={<Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>刷新</Button>}
      />

      <Row gutter={[16, 16]} align="top">
        <Col xs={24} lg={12}>
          <Card title={<span><AppstoreOutlined /> 种植单元</span>} style={cardStyle} styles={{ body: { padding: 12 } }}>
            <Table rowKey="id" size="small" loading={loading} dataSource={units} columns={unitColumns} pagination={false} scroll={{ x: 760 }} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={<span><FormOutlined /> 近期农事</span>} style={cardStyle}>
            {recent.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无近期农事" style={{ marginBlock: 10 }} /> : (
              <Space direction="vertical" style={{ width: '100%' }}>
                {recent.slice(0, 8).map((item) => (
                  <div key={`${item.source_type}-${item.source_id}`} style={{ borderBottom: `1px solid ${palette.borderSoft}`, paddingBottom: 10 }}>
                    <Space>
                      <Tag color={item.source_type === 'work_order' ? 'blue' : 'default'}>{item.source_type}</Tag>
                      <strong>{item.operation_type}</strong>
                      <span style={{ color: palette.textMuted }}>{item.operation_date}</span>
                    </Space>
                    <div style={{ color: palette.textMuted, marginTop: 4 }}>{item.cycle_name || '未关联茬口'} · {item.scope_text || item.note || '无备注'}</div>
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Card title={`作业单 · 共 ${orderTotal} 条`} style={cardStyle} styles={{ body: { padding: 12 } }}>
        <Table rowKey="id" size="small" loading={loading} dataSource={workOrders} columns={orderColumns} pagination={false} scroll={{ x: 880 }} />
      </Card>

      <Modal title="新建种植单元" open={unitOpen} onOk={createUnit} onCancel={() => setUnitOpen(false)} width={560}>
        <Form form={unitForm} layout="vertical">
          <Form.Item name="cycle_id" label="茬口" rules={[{ required: true, message: '请选择茬口' }]}>
            <Select options={cycles.map((cycle) => ({ value: cycle.id, label: cycle.name }))} />
          </Form.Item>
          <Form.Item name="name" label="单元名称" rules={[{ required: true, message: '请输入单元名称' }]}><Input placeholder="东棚 A 区" /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="area_mu" label="面积（亩）"><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={12}><Form.Item name="planted_date" label="种植日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="status" label="状态" initialValue="active"><Select options={statusOptions} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="新建农事作业单" open={orderOpen} onOk={createWorkOrder} onCancel={() => setOrderOpen(false)} width={680}>
        <Form form={orderForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="cycle_id" label="茬口">
                <Select allowClear options={cycles.map((cycle) => ({ value: cycle.id, label: cycle.name }))} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="operation_type" label="作业类型" rules={[{ required: true, message: '请选择作业类型' }]}>
                <Select showSearch options={operationOptions} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="operation_date" label="作业日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={12}><Form.Item name="scope_type" label="作业范围" initialValue="cycle"><Select options={[{ value: 'cycle', label: '整茬口' }, { value: 'unit', label: '指定单元' }]} /></Form.Item></Col>
          </Row>
          <Form.Item name="unit_ids" label="指定单元">
            <Select mode="multiple" options={units.map((unit) => ({ value: unit.id, label: unit.name }))} />
          </Form.Item>
          <Alert type="info" showIcon message="可选录入一条人工明细，系统会同步人工成本账单。" style={{ marginBottom: 12 }} />
          <Form.Item name="worker_id" label="工人">
            <Select allowClear options={workers.map((worker) => ({ value: worker.id, label: worker.name }))} />
          </Form.Item>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="quantity" label="数量"><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="unit_price" label="单价"><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="paid_amount" label="已付"><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

function LaborPanel({ cycles }: { cycles: CropCycleListItem[] }) {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [summaries, setSummaries] = useState<WorkerLaborSummary[]>([]);
  const [operationOptions, setOperationOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [unsettled, setUnsettled] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [workerOpen, setWorkerOpen] = useState(false);
  const [wageOpen, setWageOpen] = useState(false);
  const [workerForm] = Form.useForm<WorkerForm>();
  const [wageForm] = Form.useForm<WageForm>();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [workersRes, summariesRes, unsettledRes, typesRes] = await Promise.all([
        operationsApi.listWorkers(),
        operationsApi.listWorkerSummaries(),
        operationsApi.getUnsettledLaborSummary(),
        operationsApi.listOperationTypes(),
      ]);
      setWorkers(workersRes.data);
      setSummaries(summariesRes.data.items);
      setUnsettled(unsettledRes.data);
      setOperationOptions(normalizeOperationOptions(typesRes.data));
    } catch {
      message.error('加载用工数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createWorker = async () => {
    const values = await workerForm.validateFields();
    await operationsApi.createWorker(buildRequestBody(values) as Omit<Worker, 'id' | 'farm_id' | 'created_at'>);
    message.success('工人档案已创建');
    setWorkerOpen(false);
    workerForm.resetFields();
    await refresh();
  };

  const saveWage = async () => {
    const values = await wageForm.validateFields();
    await operationsApi.saveWage({
      ...buildRequestBody({
        ...values,
        work_date: values.work_date.format('YYYY-MM-DD'),
      }),
      client_request_id: createClientRequestId('wage'),
    } as WageForm & { work_date: string; client_request_id: string });
    message.success('工资记录已保存并同步成本');
    setWageOpen(false);
    wageForm.resetFields();
    await refresh();
  };

  const columns: ColumnsType<WorkerLaborSummary> = [
    { title: '工人', dataIndex: 'name', render: (text: string, record) => <Space><strong>{text}</strong>{statusTag(record.status)}</Space> },
    { title: '电话', dataIndex: 'phone', render: (value) => value || '-' },
    { title: '默认计薪', dataIndex: 'default_pay_type', render: (value) => payTypeOptions.find((item) => item.value === value)?.label || value },
    { title: '应付', dataIndex: 'total_payable', render: formatMoney },
    { title: '已付', dataIndex: 'total_paid', render: formatMoney },
    { title: '未付', dataIndex: 'total_unpaid', render: (value) => <strong style={{ color: Number(value) > 0 ? palette.warning : palette.textMuted }}>{formatMoney(value)}</strong> },
    { title: '记录数', dataIndex: 'entry_count' },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><MetricCard><Statistic title="工人数量" value={workers.length} prefix={<TeamOutlined />} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.warning}><Statistic title="未结摘要字段" value={unsettled ? Object.keys(unsettled).length : 0} prefix={<DollarOutlined />} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.success}><Statistic title="启用工人" value={workers.filter((worker) => worker.status === 'active').length} prefix={<CheckCircleOutlined />} /></MetricCard></Col>
      </Row>
      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => {
              workerForm.setFieldsValue({ default_pay_type: 'daily', status: 'active' });
              setWorkerOpen(true);
            }}>新建工人</Button>
            <Button icon={<DollarOutlined />} onClick={() => {
              wageForm.setFieldsValue({ pay_type: 'daily', quantity: 1, paid_amount: 0, work_date: dayjs() });
              setWageOpen(true);
            }}>独立记工资</Button>
          </>
        )}
        right={<Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>刷新</Button>}
      />
      <Card style={cardStyle} styles={{ body: { padding: 12 } }}>
        <Table rowKey="id" size="small" loading={loading} dataSource={summaries} columns={columns} scroll={{ x: 920 }} />
      </Card>
      <Card title="未结人工原始响应" style={cardStyle}>
        <pre style={{ margin: 0, color: palette.textMuted, whiteSpace: 'pre-wrap' }}>{JSON.stringify(unsettled ?? {}, null, 2)}</pre>
      </Card>

      <Modal title="新建工人" open={workerOpen} onOk={createWorker} onCancel={() => setWorkerOpen(false)} width={560}>
        <Form form={workerForm} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="phone" label="电话"><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="default_pay_type" label="默认计薪" initialValue="daily"><Select options={payTypeOptions} /></Form.Item></Col>
            <Col span={12}><Form.Item name="default_unit_price" label="默认单价"><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="status" label="状态" initialValue="active"><Select options={statusOptions} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="独立记工资" open={wageOpen} onOk={saveWage} onCancel={() => setWageOpen(false)} width={640}>
        <Form form={wageForm} layout="vertical">
          <Row gutter={12}>
            <Col span={12}><Form.Item name="cycle_id" label="茬口" rules={[{ required: true }]}><Select options={cycles.map((cycle) => ({ value: cycle.id, label: cycle.name }))} /></Form.Item></Col>
            <Col span={12}><Form.Item name="operation_type" label="作业类型" rules={[{ required: true }]}><Select showSearch options={operationOptions} /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="worker_id" label="已有工人"><Select allowClear options={workers.map((worker) => ({ value: worker.id, label: worker.name }))} /></Form.Item></Col>
            <Col span={12}><Form.Item name="worker_name" label="新工人名称"><Input placeholder="未选择已有工人时填写" /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="work_date" label="日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="quantity" label="数量" rules={[{ required: true }]}><InputNumber min={0.01} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={8}><Form.Item name="unit_price" label="单价" rules={[{ required: true }]}><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="paid_amount" label="已付金额" initialValue={0}><InputNumber min={0} precision={2} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

function FinancePanel() {
  const [debts, setDebts] = useState<DebtListResponse | null>(null);
  const [categories, setCategories] = useState<CostCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [debtOpen, setDebtOpen] = useState(false);
  const [settleOpen, setSettleOpen] = useState(false);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [debtForm] = Form.useForm<DebtForm>();
  const [settleForm] = Form.useForm<{ counterparty: string; amount?: number | null; note?: string }>();
  const [categoryForm] = Form.useForm<CategoryForm>();
  const debtSummary = debts?.summary ?? [];

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [debtsRes, categoriesRes] = await Promise.all([
        operationsApi.listDebts({ page: 1, size: 50 }),
        operationsApi.listCostCategories(),
      ]);
      setDebts(debtsRes.data);
      setCategories(categoriesRes.data);
    } catch {
      message.error('加载财务调试数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createDebt = async () => {
    const values = await debtForm.validateFields();
    await operationsApi.createDebt(buildRequestBody({
      record_type: 'cost',
      record_subtype: 'debt',
      counterparty: values.counterparty,
      amount: String(values.amount),
      category: values.category,
      record_date: values.record_date.format('YYYY-MM-DD'),
      due_date: values.due_date?.format('YYYY-MM-DD'),
      note: values.note,
    }));
    message.success('赊账记录已创建');
    setDebtOpen(false);
    debtForm.resetFields();
    await refresh();
  };

  const settleDebt = async () => {
    const values = await settleForm.validateFields();
    await operationsApi.settleDebt(buildRequestBody(values) as { counterparty: string; amount?: string | number | null; note?: string });
    message.success('赊账已结算');
    setSettleOpen(false);
    settleForm.resetFields();
    await refresh();
  };

  const createCategory = async () => {
    const values = await categoryForm.validateFields();
    await operationsApi.createCostCategory(values);
    message.success('分类已创建');
    setCategoryOpen(false);
    categoryForm.resetFields();
    await refresh();
  };

  const debtColumns: ColumnsType<DebtListResponse['items'][number]> = [
    { title: 'ID', dataIndex: 'id', width: 64 },
    { title: '债权人', dataIndex: 'counterparty', render: (value) => value || '-' },
    { title: '金额', dataIndex: 'amount', render: formatMoney },
    { title: '分类', dataIndex: 'category' },
    { title: '日期', dataIndex: 'record_date' },
    { title: '到期', dataIndex: 'due_date', render: (value) => value || '-' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
  ];

  const categoryColumns: ColumnsType<CostCategory> = [
    { title: '名称', dataIndex: 'name', render: (text: string, record) => <Space><strong>{text}</strong>{record.is_default && <Tag>预设</Tag>}</Space> },
    { title: '类型', dataIndex: 'type', render: (value) => <Tag color={value === 'cost' ? 'red' : 'green'}>{value === 'cost' ? '支出' : '收入'}</Tag> },
    { title: '图标', dataIndex: 'icon' },
    { title: '排序', dataIndex: 'sort_order', width: 80 },
    {
      title: '操作',
      width: 100,
      render: (_, record) => record.is_default ? '-' : (
        <Popconfirm title="确认删除" onConfirm={async () => {
          await operationsApi.deleteCostCategory(record.id);
          message.success('分类已删除');
          await refresh();
        }}>
          <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><MetricCard accent={palette.warning}><Statistic title="未结债权人" value={debtSummary.length} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.danger}><Statistic title="未结总额" value={debtSummary.reduce((sum, item) => sum + Number(item.remaining), 0)} precision={2} prefix="¥" /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard><Statistic title="成本分类" value={categories.length} /></MetricCard></Col>
      </Row>
      <Toolbar
        left={(
          <>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => {
              debtForm.setFieldsValue({ category: '赊账', record_date: dayjs() });
              setDebtOpen(true);
            }}>创建赊账</Button>
            <Button icon={<CheckCircleOutlined />} onClick={() => setSettleOpen(true)}>结算赊账</Button>
            <Button icon={<PlusOutlined />} onClick={() => {
              categoryForm.setFieldsValue({ type: 'cost', icon: 'other', sort_order: categories.length + 1 });
              setCategoryOpen(true);
            }}>新建分类</Button>
          </>
        )}
        right={<Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>刷新</Button>}
      />
      <Row gutter={[16, 16]} align="top">
        <Col xs={24} xl={13}>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Card title="赊账记录" style={cardStyle} styles={{ body: { padding: 12 } }}>
              <Table rowKey="id" size="small" loading={loading} dataSource={debts?.items ?? []} columns={debtColumns} scroll={{ x: 820 }} />
            </Card>
            <Card title="赊账摘要" style={cardStyle}>
              <Row gutter={[12, 12]}>
                {debtSummary.map((item) => (
                  <Col xs={24} md={8} key={item.counterparty}>
                    <Card size="small" style={{ background: palette.bgPanel, borderColor: palette.border }}>
                      <Typography.Text strong>{item.counterparty}</Typography.Text>
                      <div style={{ color: palette.textMuted, marginTop: 8 }}>剩余 {formatMoney(item.remaining)} · {item.record_count} 条</div>
                    </Card>
                  </Col>
                ))}
                {debtSummary.length === 0 && <Col span={24}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无未结赊账" style={{ marginBlock: 10 }} /></Col>}
              </Row>
            </Card>
          </Space>
        </Col>
        <Col xs={24} xl={11}>
          <Card title="成本分类" style={cardStyle} styles={{ body: { padding: 12 } }}>
            <Table rowKey="id" size="small" loading={loading} dataSource={categories} columns={categoryColumns} pagination={false} scroll={{ x: 620 }} />
          </Card>
        </Col>
      </Row>

      <Modal title="创建赊账记录" open={debtOpen} onOk={createDebt} onCancel={() => setDebtOpen(false)} width={560}>
        <Form form={debtForm} layout="vertical">
          <Form.Item name="counterparty" label="债权人" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="amount" label="金额" rules={[{ required: true }]}><InputNumber min={0.01} precision={2} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="category" label="分类" rules={[{ required: true }]}><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="record_date" label="记录日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={12}><Form.Item name="due_date" label="到期日期"><DatePicker style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="结算赊账" open={settleOpen} onOk={settleDebt} onCancel={() => setSettleOpen(false)} width={520}>
        <Form form={settleForm} layout="vertical">
          <Form.Item name="counterparty" label="债权人" rules={[{ required: true }]}><Select showSearch options={debtSummary.map((item) => ({ value: item.counterparty, label: `${item.counterparty} · 剩余 ${formatMoney(item.remaining)}` }))} /></Form.Item>
          <Form.Item name="amount" label="还款金额"><InputNumber min={0.01} precision={2} style={{ width: '100%' }} placeholder="不填则全额结清" /></Form.Item>
          <Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>

      <Modal title="新建成本分类" open={categoryOpen} onOk={createCategory} onCancel={() => setCategoryOpen(false)} width={520}>
        <Form form={categoryForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="type" label="类型" initialValue="cost"><Select options={[{ value: 'cost', label: '支出' }, { value: 'income', label: '收入' }]} /></Form.Item>
          <Form.Item name="icon" label="图标" initialValue="other"><Select options={defaultCategoryIcons} /></Form.Item>
          <Form.Item name="sort_order" label="排序" initialValue={0}><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

function SystemPanel() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [feedback, setFeedback] = useState<Record<string, unknown> | null>(null);
  const [version, setVersion] = useState<VersionCheck | null>(null);
  const [appSkills, setAppSkills] = useState<AppSkillListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [settingsForm] = Form.useForm<SettingsForm>();
  const [versionCode, setVersionCode] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [settingsRes, feedbackRes, versionRes] = await Promise.all([
        operationsApi.getSettings(),
        operationsApi.getFeedbackStats(),
        operationsApi.checkVersion(versionCode),
      ]);
      setSettings(settingsRes.data);
      setFeedback(feedbackRes.data);
      setVersion(versionRes.data);
      settingsForm.setFieldsValue({
        ...settingsRes.data,
        default_city: settingsRes.data.default_city ?? undefined,
        assistant_role: settingsRes.data.assistant_role ?? 'warm',
      });
    } catch {
      message.error('加载用户与应用调试数据失败');
    } finally {
      setLoading(false);
    }
  }, [settingsForm, versionCode]);

  const refreshAppSkills = useCallback(async () => {
    setSkillsLoading(true);
    try {
      const data = await listAppSkills();
      setAppSkills(data);
    } catch {
      message.error('加载 App 技能列表失败');
    } finally {
      setSkillsLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    refreshAppSkills();
  }, [refreshAppSkills]);

  const updateSettings = async () => {
    const values = await settingsForm.validateFields();
    const res = await operationsApi.updateSettings(buildRequestBody(values));
    setSettings(res.data);
    message.success('用户设置已更新');
  };

  const skillColumns: ColumnsType<AppSkillItem> = [
    { title: 'Key', dataIndex: 'key', width: 180 },
    { title: '名称', dataIndex: 'title', width: 120, render: (text: string) => <strong>{text}</strong> },
    { title: '分类', dataIndex: 'category', width: 90, render: (value: string) => <Tag color="blue">{value}</Tag> },
    { title: '图标', dataIndex: 'icon', width: 130 },
    { title: '颜色', dataIndex: 'icon_color', width: 90 },
    { title: '推荐', dataIndex: 'recommended', width: 80, render: (value: boolean) => value ? <Tag color="success">是</Tag> : <Tag>否</Tag> },
    { title: '启用', dataIndex: 'enabled', width: 80, render: (value: boolean) => value ? <Tag color="success">是</Tag> : <Tag color="default">否</Tag> },
    { title: '描述', dataIndex: 'description', ellipsis: true },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Toolbar
        left={(
          <>
            <InputNumber value={versionCode} min={0} onChange={(value) => setVersionCode(value ?? 0)} addonBefore="当前版本码" />
            <Button icon={<CloudDownloadOutlined />} onClick={refresh} loading={loading}>检查版本</Button>
          </>
        )}
        right={<Button icon={<ReloadOutlined />} onClick={refresh} loading={loading}>刷新全部</Button>}
      />
      <Card
        title={<span><AppstoreOutlined /> App 技能列表接口</span>}
        extra={(
          <Button icon={<ReloadOutlined />} onClick={refreshAppSkills} loading={skillsLoading}>
            调试 GET /agent/skills
          </Button>
        )}
        style={cardStyle}
        styles={{ body: { padding: 12 } }}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Alert
            type="info"
            showIcon
            message={`当前接口：GET /agent/skills${appSkills ? `，返回 ${appSkills.total} 个技能` : ''}`}
          />
          <Table
            rowKey="key"
            size="small"
            loading={skillsLoading}
            dataSource={appSkills?.items ?? []}
            columns={skillColumns}
            pagination={false}
            scroll={{ x: 980 }}
          />
          <pre style={rawPreviewStyle}>{JSON.stringify(appSkills ?? {}, null, 2)}</pre>
        </Space>
      </Card>
      <Row gutter={[16, 16]} align="top">
        <Col xs={24} lg={12}>
          <Card title={<span><SettingOutlined /> 当前用户设置</span>} style={cardStyle}>
            <Form form={settingsForm} layout="vertical">
              <Form.Item name="display_name" label="显示名" rules={[{ required: true }]}><Input /></Form.Item>
              <Form.Item name="default_city" label="默认城市"><Input /></Form.Item>
              <Form.Item
                name="assistant_role"
                label="回答风格"
                initialValue="warm"
                tooltip="控制芽芽回复时使用的语气提示词"
              >
                <Select
                  optionLabelProp="title"
                  options={assistantRoleOptions.map((option) => ({
                    value: option.value,
                    title: option.label,
                    label: (
                      <Space direction="vertical" size={0}>
                        <span>{option.label}</span>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {option.description}
                        </Typography.Text>
                      </Space>
                    ),
                  }))}
                />
              </Form.Item>
              <Row gutter={12}>
                <Col span={12}><Form.Item name="default_lat" label="纬度"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
                <Col span={12}><Form.Item name="default_lon" label="经度"><InputNumber style={{ width: '100%' }} /></Form.Item></Col>
              </Row>
              <Button type="primary" onClick={updateSettings}>保存设置</Button>
            </Form>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title={<span><CloudDownloadOutlined /> App 版本</span>} style={cardStyle}>
            {version ? (
              <Descriptions column={1}>
                <Descriptions.Item label="最新版本">{version.latest_version}</Descriptions.Item>
                <Descriptions.Item label="版本码">{version.latest_version_code}</Descriptions.Item>
                <Descriptions.Item label="强制更新"><Tag color={version.force_update ? 'red' : 'default'}>{version.force_update ? '是' : '否'}</Tag></Descriptions.Item>
                <Descriptions.Item label="下载地址">{version.download_url || '-'}</Descriptions.Item>
                <Descriptions.Item label="更新日志">{version.changelog || '-'}</Descriptions.Item>
              </Descriptions>
            ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginBlock: 10 }} />}
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}><MetricCard><Statistic title="好评" value={Number(feedback?.good ?? 0)} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.danger}><Statistic title="差评" value={Number(feedback?.bad ?? 0)} /></MetricCard></Col>
        <Col xs={24} md={8}><MetricCard accent={palette.purple}><Statistic title="反馈字段" value={feedback ? Object.keys(feedback).length : 0} /></MetricCard></Col>
      </Row>
      <Card title="反馈统计原始响应" style={cardStyle}>
        <pre style={{ margin: 0, color: palette.textMuted, whiteSpace: 'pre-wrap' }}>{JSON.stringify({ settings, feedback }, null, 2)}</pre>
      </Card>
    </Space>
  );
}
